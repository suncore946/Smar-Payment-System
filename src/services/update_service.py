"""
双模版本管理与自动更新核心服务 (src/services/update_service.py)
支持：
1. Git 仓库零成本托管模式：
   - GitHub Releases API (`owner/repo` 或 `https://github.com/owner/repo`)
   - Gitee 码云 Releases API (`owner/repo` 或 `https://gitee.com/owner/repo`，国内直连免代理)
   - Git Raw / 静态托管 `version.json` 清单文件
2. 自建服务器 / 对象存储 (OSS / COS / Nginx / 局域网共享路径) `version.json` 清单模式
3. 增量词库热更新 (`hot_keywords`) + 完整单文件 `.exe` 流式下载、SHA256 校验与 Windows 无缝自替换重启脚本
4. 打包时自动生成带 SHA256 签名与字节大小的 `dist/version.json` 发布清单
"""

from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request

from src.version import (
    APP_BUILD_DATE,
    APP_CHANNEL,
    APP_NAME,
    APP_VERSION,
    CHANGELOG_HISTORY,
    OFFICIAL_GITHUB_REPO,
    is_newer_version,
)


@dataclass
class ReleaseManifest:
    """远端或本地构建生成的版本发布清单值对象"""
    version: str
    release_date: str = APP_BUILD_DATE
    channel: str = APP_CHANNEL
    download_url: str = ""
    sha256: str = ""
    file_size: int = 0
    force_update: bool = False
    release_notes: str = ""
    hot_keywords: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_name": APP_NAME,
            "version": self.version,
            "release_date": self.release_date,
            "channel": self.channel,
            "download_url": self.download_url,
            "sha256": self.sha256,
            "file_size": self.file_size,
            "force_update": self.force_update,
            "release_notes": self.release_notes,
            "hot_keywords": self.hot_keywords,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReleaseManifest":
        ver = str(data.get("version") or data.get("tag_name") or "0.0.0").lstrip("vV")
        r_date = str(data.get("release_date") or data.get("published_at") or "")[:10]
        notes = data.get("release_notes") or data.get("body") or ""
        if isinstance(notes, list):
            notes = "\n".join(f"• {line}" for line in notes)
        hot_kw = data.get("hot_keywords")
        if not isinstance(hot_kw, dict):
            hot_kw = {}
        return cls(
            version=ver,
            release_date=r_date or APP_BUILD_DATE,
            channel=str(data.get("channel") or "stable"),
            download_url=str(data.get("download_url") or ""),
            sha256=str(data.get("sha256") or "").lower().strip(),
            file_size=int(data.get("file_size") or 0),
            force_update=bool(data.get("force_update", False)),
            release_notes=str(notes),
            hot_keywords=hot_kw,
        )


@dataclass
class UpdateCheckResult:
    """版本检查结果封装"""
    success: bool
    has_update: bool
    current_version: str
    latest_version: str
    manifest: Optional[ReleaseManifest] = None
    message: str = ""


class AutoUpdateService:
    """面向对象版本管理与自动更新核心服务"""

    USER_AGENT = f"LotteryRiskPro-Updater/{APP_VERSION} (Windows; PyQt5)"

    @staticmethod
    def compute_file_sha256(file_path: str | Path) -> str:
        """计算本地文件的 SHA256 哈希值"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest().lower()

    @classmethod
    def resolve_check_endpoint(cls, source_mode: str, repo_or_url: str) -> str:
        """
        将用户输入的仓库名 (`owner/repo`)、Git 仓库主页或自定义 URL 解析为标准请求地址：
        - github_api: 支持 `owner/repo` 或 `https://github.com/owner/repo` -> `https://api.github.com/repos/owner/repo/releases/latest`
        - gitee_api: 支持 `owner/repo` 或 `https://gitee.com/owner/repo` -> `https://gitee.com/api/v5/repos/owner/repo/releases/latest`
        - github_or_json / custom_json: 直接请求该 JSON URL 或本地路径
        """
        raw = (repo_or_url or "").strip()
        if not raw:
            return ""

        # 若用户填的是简写 owner/repo
        repo_match = re.match(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)$", raw)
        if source_mode == "github_api":
            if repo_match:
                return f"https://api.github.com/repos/{repo_match.group(1)}/releases/latest"
            m_gh = re.search(r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", raw)
            if m_gh and "/releases/" not in raw and not raw.endswith(".json"):
                repo_slug = m_gh.group(1).removesuffix(".git")
                return f"https://api.github.com/repos/{repo_slug}/releases/latest"
        elif source_mode == "gitee_api":
            if repo_match:
                return f"https://gitee.com/api/v5/repos/{repo_match.group(1)}/releases/latest"
            m_gt = re.search(r"gitee\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", raw)
            if m_gt and "/releases/" not in raw and not raw.endswith(".json"):
                repo_slug = m_gt.group(1).removesuffix(".git")
                return f"https://gitee.com/api/v5/repos/{repo_slug}/releases/latest"

        return raw

    @classmethod
    def apply_mirror_prefix(cls, download_url: str, mirror_prefix: str = "") -> str:
        """为 GitHub 下载链接应用可选的国内加速镜像前缀（如 https://ghfast.top/）"""
        url = (download_url or "").strip()
        prefix = (mirror_prefix or "").strip()
        if not url or not prefix:
            return url
        if not prefix.endswith("/"):
            prefix += "/"
        if ("github.com" in url or "githubusercontent.com" in url) and not url.startswith(prefix):
            return f"{prefix}{url}"
        return url

    @classmethod
    def _fetch_json_from_endpoint(cls, endpoint: str, timeout: float = 6.0) -> Dict[str, Any]:
        """从 HTTP/HTTPS URL、file:// URL 或本地文件路径读取 JSON 数据"""
        p = Path(endpoint)
        if p.exists() and p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))

        if endpoint.startswith("file://"):
            parsed = urllib.parse.urlparse(endpoint)
            local_p = Path(urllib.request.url2pathname(parsed.path))
            return json.loads(local_p.read_text(encoding="utf-8"))

        req = urllib.request.Request(
            endpoint,
            headers={
                "User-Agent": cls.USER_AGENT,
                "Accept": "application/vnd.github+json, application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
            return json.loads(raw_bytes.decode("utf-8", errors="replace"))

    @classmethod
    def parse_remote_payload(
        cls, payload: Dict[str, Any], mirror_prefix: str = "", timeout: float = 6.0
    ) -> ReleaseManifest:
        """
        智能兼容两种远端 JSON 格式：
        1. 标准 `version.json` 清单格式（包含 `version`, `download_url`, `sha256`, `release_notes`）
        2. GitHub / Gitee Releases API 响应格式（包含 `tag_name`, `body`, `assets` 列表）：
           - 若 `assets` 中包含 `version.json`，优先拉取 `version.json` 以获取精确 SHA256；
           - 否则自动选取 `assets` 中的 `.exe` 安装包作为 `download_url`。
        """
        if "assets" in payload and isinstance(payload["assets"], list):
            assets = payload["assets"]
            exe_asset = None
            json_asset = None
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                name = str(asset.get("name") or "").lower()
                dl_url = str(asset.get("browser_download_url") or "")
                if name == "version.json" and dl_url:
                    json_asset = asset
                elif name.endswith(".exe") and dl_url:
                    exe_asset = asset

            if json_asset:
                try:
                    json_url = cls.apply_mirror_prefix(
                        str(json_asset["browser_download_url"]), mirror_prefix
                    )
                    sub_payload = cls._fetch_json_from_endpoint(json_url, timeout=timeout)
                    manifest = ReleaseManifest.from_dict(sub_payload)
                    if not manifest.download_url and exe_asset:
                        manifest.download_url = str(exe_asset.get("browser_download_url") or "")
                    return manifest
                except Exception:
                    pass

            ver = str(payload.get("tag_name") or payload.get("version") or "0.0.0").lstrip("vV")
            dl_url = str(exe_asset.get("browser_download_url") or "") if exe_asset else ""
            f_size = int(exe_asset.get("size") or 0) if exe_asset else 0
            pub_date = str(payload.get("published_at") or payload.get("created_at") or APP_BUILD_DATE)[:10]
            return ReleaseManifest(
                version=ver,
                release_date=pub_date,
                download_url=dl_url,
                sha256="",
                file_size=f_size,
                force_update=False,
                release_notes=str(payload.get("body") or ""),
            )

        return ReleaseManifest.from_dict(payload)

    @classmethod
    def check_for_updates(
        cls,
        source_mode: str,
        repo_or_url: str,
        mirror_prefix: str = "",
        current_version: str = APP_VERSION,
        timeout: float = 6.0,
    ) -> UpdateCheckResult:
        """执行远端版本检查并返回结构化结果"""
        endpoint = cls.resolve_check_endpoint(source_mode, repo_or_url)
        if not endpoint:
            return UpdateCheckResult(
                success=False,
                has_update=False,
                current_version=current_version,
                latest_version=current_version,
                message="尚未配置更新服务器或 Git 仓库地址。",
            )

        fetch_url = cls.apply_mirror_prefix(endpoint, mirror_prefix)
        try:
            payload = cls._fetch_json_from_endpoint(fetch_url, timeout=timeout)
            manifest = cls.parse_remote_payload(payload, mirror_prefix=mirror_prefix, timeout=timeout)
            has_new = is_newer_version(manifest.version, current_version)
            msg = (
                f"发现新版本 v{manifest.version}（当前版本 v{current_version}）！"
                if has_new
                else f"当前已是最新版本 (v{current_version})。"
            )
            return UpdateCheckResult(
                success=True,
                has_update=has_new,
                current_version=current_version,
                latest_version=manifest.version,
                manifest=manifest,
                message=msg,
            )
        except Exception as exc:
            return UpdateCheckResult(
                success=False,
                has_update=False,
                current_version=current_version,
                latest_version=current_version,
                message=f"无法连接更新源 ({endpoint})：{exc}",
            )

    @classmethod
    def download_and_verify_release(
        cls,
        manifest: ReleaseManifest,
        dest_path: str | Path,
        mirror_prefix: str = "",
        progress_callback: Optional[Callable[[int, int], None]] = None,
        timeout: float = 30.0,
    ) -> Path:
        """
        下载新版安装文件到指定路径，实时回调下载进度，并在提供 SHA256 时严格校验文件完整性
        """
        if not manifest.download_url:
            raise ValueError("远端发布清单中未包含可执行文件下载地址 (download_url)")

        target = Path(dest_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        dl_url = cls.apply_mirror_prefix(manifest.download_url, mirror_prefix)

        src_file = Path(dl_url)
        if src_file.exists() and src_file.is_file():
            shutil.copy2(src_file, target)
            if progress_callback:
                sz = target.stat().st_size
                progress_callback(sz, sz)
        elif dl_url.startswith("file://"):
            parsed = urllib.parse.urlparse(dl_url)
            local_p = Path(urllib.request.url2pathname(parsed.path))
            shutil.copy2(local_p, target)
            if progress_callback:
                sz = target.stat().st_size
                progress_callback(sz, sz)
        else:
            req = urllib.request.Request(dl_url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(target, "wb") as out_f:
                total = int(resp.headers.get("Content-Length") or manifest.file_size or 0)
                downloaded = 0
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

        if manifest.sha256:
            actual_hash = cls.compute_file_sha256(target)
            if actual_hash.lower() != manifest.sha256.lower():
                target.unlink(missing_ok=True)
                raise ValueError(
                    f"下载文件 SHA256 签名校验不匹配！\n预期: {manifest.sha256}\n实际: {actual_hash}"
                )

        return target

    @classmethod
    def create_windows_self_update_script(cls, current_exe: Path, downloaded_exe: Path) -> Path:
        """
        生成 Windows 单文件 `.exe` 无缝自替换升级批处理脚本：
        等待当前进程退出 -> 备份旧版 `.exe.bak` -> 将新版 `.exe` 移动覆盖到原路径 -> 重新拉起新版 `.exe` -> 清理临时文件
        """
        script_path = Path(tempfile.gettempdir()) / "lottery_pro_self_updater.bat"
        cur_str = str(current_exe.resolve())
        new_str = str(downloaded_exe.resolve())
        bak_str = str(current_exe.with_suffix(".exe.bak").resolve())

        bat_content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "echo 正在升级 特码智能收单与吃码风控系统 Pro，请稍候...\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            ":retry_move\r\n"
            f'if exist "{bak_str}" del /f /q "{bak_str}" >nul 2>&1\r\n'
            f'move /y "{cur_str}" "{bak_str}" >nul 2>&1\r\n'
            "if errorlevel 1 (\r\n"
            "    timeout /t 1 /nobreak >nul\r\n"
            "    goto retry_move\r\n"
            ")\r\n"
            f'move /y "{new_str}" "{cur_str}" >nul 2>&1\r\n'
            f'if exist "{bak_str}" del /f /q "{bak_str}" >nul 2>&1\r\n'
            f'start "" "{cur_str}"\r\n'
            'del "%~f0" >nul 2>&1\r\n'
        )
        script_path.write_text(bat_content, encoding="utf-8")
        return script_path

    @classmethod
    def trigger_self_update_and_restart(cls, downloaded_exe: Path) -> bool:
        """
        若当前处于打包后的 `.exe` 环境 (`sys.frozen`)，启动后台自替换脚本并退出当前进程；
        若处于 Python 源码运行环境，提示已下载的新版 `.exe` 保存路径。
        """
        if not getattr(sys, "frozen", False):
            return False

        current_exe = Path(sys.executable).resolve()
        bat_script = cls.create_windows_self_update_script(current_exe, downloaded_exe)
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_script)],
            cwd=str(current_exe.parent),
            creationflags=creation_flags,
            close_fds=True,
        )
        return True

    @classmethod
    def generate_version_manifest_file(
        cls,
        exe_path: str | Path,
        output_json_path: str | Path,
        download_url: str = "",
    ) -> ReleaseManifest:
        """
        根据打包生成的 `.exe` 自动计算 SHA256 与文件大小，输出标准 `version.json` 清单文件
        （可直接上传至 GitHub/Gitee 仓库或任意自定义静态服务器）
        """
        exe_p = Path(exe_path)
        sha256_str = cls.compute_file_sha256(exe_p) if exe_p.exists() else ""
        size_bytes = exe_p.stat().st_size if exe_p.exists() else 0
        latest_notes = (
            "\n".join(f"• {item}" for item in CHANGELOG_HISTORY[0].highlights)
            if CHANGELOG_HISTORY
            else f"发布 {APP_NAME} v{APP_VERSION}"
        )
        if not download_url:
            download_url = (
                f"https://github.com/{OFFICIAL_GITHUB_REPO}/releases/download/v{APP_VERSION}/{exe_p.name}"
            )

        manifest = ReleaseManifest(
            version=APP_VERSION,
            release_date=APP_BUILD_DATE,
            channel=APP_CHANNEL,
            download_url=download_url,
            sha256=sha256_str,
            file_size=size_bytes,
            force_update=False,
            release_notes=latest_notes,
            hot_keywords={},
        )
        out_p = Path(output_json_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest
