"""
版本检测、下载进度校验与一键自更新弹窗组件 (src/ui/update_dialog.py)
采用 QThread 异步非阻塞架构：
1. 后台异步请求 GitHub / Gitee Releases API 或自定义服务器 `version.json`
2. 发现新版本后展示更新日志、SHA256 签名与文件大小
3. 支持带实时进度条的流式下载、SHA256 完整性校验、增量词库热更新及 Windows `.exe` 无缝自替换重启
"""

from __future__ import annotations
from pathlib import Path
import sys
import tempfile
from typing import Optional
from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from src.services.app_controller import ApplicationController
from src.services.update_service import AutoUpdateService, ReleaseManifest, UpdateCheckResult
from src.ui.icon_manager import CartoonIconManager
from src.version import APP_BUILD_DATE, APP_VERSION, CHANGELOG_HISTORY, OFFICIAL_GITHUB_REPO


class UpdateCheckWorker(QThread):
    """后台异步版本检查线程"""

    finished_check = pyqtSignal(object)  # UpdateCheckResult

    def __init__(self, controller: ApplicationController, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.controller = controller

    def run(self) -> None:
        res = self.controller.check_for_updates(timeout=6.0)
        self.finished_check.emit(res)


class UpdateDownloadWorker(QThread):
    """后台异步安装包流式下载与 SHA256 校验线程"""

    progress_changed = pyqtSignal(int, int)  # downloaded_bytes, total_bytes
    download_succeeded = pyqtSignal(str)     # local file path
    download_failed = pyqtSignal(str)        # error message

    def __init__(
        self,
        manifest: ReleaseManifest,
        dest_path: Path,
        mirror_prefix: str = "",
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self.manifest = manifest
        self.dest_path = dest_path
        self.mirror_prefix = mirror_prefix

    def run(self) -> None:
        try:
            saved_path = AutoUpdateService.download_and_verify_release(
                manifest=self.manifest,
                dest_path=self.dest_path,
                mirror_prefix=self.mirror_prefix,
                progress_callback=lambda cur, tot: self.progress_changed.emit(cur, tot),
                timeout=60.0,
            )
            self.download_succeeded.emit(str(saved_path))
        except Exception as exc:
            self.download_failed.emit(str(exc))


class UpdateDialog(QDialog):
    """版本管理、更新日志查看与一键在线升级对话框"""

    def __init__(
        self,
        controller: ApplicationController,
        initial_result: Optional[UpdateCheckResult] = None,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._check_result: Optional[UpdateCheckResult] = initial_result
        self._check_worker: Optional[UpdateCheckWorker] = None
        self._dl_worker: Optional[UpdateDownloadWorker] = None

        self.setWindowTitle(f"🚀 版本管理与在线升级中心 — 当前版本 v{APP_VERSION}")
        self.setWindowIcon(CartoonIconManager.get_icon("act_update"))
        self.resize(680, 520)
        self._init_ui()

        if initial_result is not None:
            self._render_check_result(initial_result)
        else:
            self._render_default_changelog()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 顶部版本信息卡片
        top_card = QFrame()
        top_card.setProperty("card", True)
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(14, 12, 14, 12)
        top_layout.setSpacing(12)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(CartoonIconManager.render_pixmap("act_update", 48))
        top_layout.addWidget(lbl_icon)

        info_col = QVBoxLayout()
        self.lbl_ver_headline = QLabel(
            f"<b>特码智能收单与吃码风控系统 Pro — 当前版本：v{APP_VERSION}</b> (构建日期: {APP_BUILD_DATE})"
        )
        self.lbl_ver_headline.setStyleSheet("font-size: 14px;")
        self.lbl_status_sub = QLabel(
            f"官方更新源：{OFFICIAL_GITHUB_REPO} (🔒 已锁定防篡改)"
        )
        self.lbl_status_sub.setProperty("mutedText", True)
        self.lbl_status_sub.setWordWrap(True)
        info_col.addWidget(self.lbl_ver_headline)
        info_col.addWidget(self.lbl_status_sub)
        top_layout.addLayout(info_col, 1)

        self.btn_check_now = QPushButton("🔍 立即检查新版本")
        self.btn_check_now.setProperty("primary", True)
        self.btn_check_now.setMinimumHeight(36)
        self.btn_check_now.clicked.connect(self.start_async_check)
        top_layout.addWidget(self.btn_check_now)

        layout.addWidget(top_card)

        # 中部：更新日志 / 远端新版本详情展示框
        self.txt_notes = QTextBrowser()
        self.txt_notes.setOpenExternalLinks(True)
        self.txt_notes.setStyleSheet("QTextBrowser { padding: 12px; font-size: 13px; line-height: 1.6; }")
        layout.addWidget(self.txt_notes, 1)

        # 下载进度条（默认隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 底部操作按钮栏
        btn_bar = QHBoxLayout()
        self.btn_skip_ver = QPushButton("⏭️ 跳过此版本")
        self.btn_skip_ver.setVisible(False)
        self.btn_skip_ver.clicked.connect(self._on_skip_version)
        btn_bar.addWidget(self.btn_skip_ver)

        self.btn_browser_dl = QPushButton("🌐 浏览器直接下载")
        self.btn_browser_dl.setVisible(False)
        self.btn_browser_dl.clicked.connect(self._on_open_browser_download)
        btn_bar.addWidget(self.btn_browser_dl)

        btn_bar.addStretch()

        self.btn_apply_update = QPushButton("🚀 立即下载并自动替换升级")
        self.btn_apply_update.setProperty("success", True)
        self.btn_apply_update.setMinimumHeight(38)
        self.btn_apply_update.setVisible(False)
        self.btn_apply_update.clicked.connect(self._on_start_download_update)
        btn_bar.addWidget(self.btn_apply_update)

        btn_close = QPushButton("关闭窗口")
        btn_close.setMinimumHeight(36)
        btn_close.clicked.connect(self.close)
        btn_bar.addWidget(btn_close)

        layout.addLayout(btn_bar)

    def _render_default_changelog(self) -> None:
        html_parts = [
            f"<h3 style='color:#1E3A8A;'>📜 历次版本发布与更新日志 (当前运行版本: v{APP_VERSION})</h3>",
            "<p>您可以点击右上角<b>「🔍 立即检查新版本」</b>连接 Git 仓库或自定义更新服务器获取最新安装包与词库补丁。</p><hr>",
        ]
        for entry in CHANGELOG_HISTORY:
            items_html = "".join(f"<li>{item}</li>" for item in entry.highlights)
            html_parts.append(
                f"<h4 style='color:#2563EB;'>🎉 版本 v{entry.version} <span style='color:#64748B;font-size:12px;'>({entry.release_date})</span></h4>"
                f"<ul>{items_html}</ul>"
            )
        self.txt_notes.setHtml("".join(html_parts))

    def start_async_check(self) -> None:
        self.btn_check_now.setEnabled(False)
        self.btn_check_now.setText("⏳ 正在连接更新源...")
        self.lbl_status_sub.setText("正在请求远端版本清单，请稍候...")
        self._check_worker = UpdateCheckWorker(self.controller, self)
        self._check_worker.finished_check.connect(self._on_check_completed)
        self._check_worker.start()

    def _on_check_completed(self, result: UpdateCheckResult) -> None:
        self.btn_check_now.setEnabled(True)
        self.btn_check_now.setText("🔍 重新检查更新")
        self._check_result = result
        self._render_check_result(result)

    def _render_check_result(self, result: UpdateCheckResult) -> None:
        self.lbl_status_sub.setText(result.message)
        if not result.success:
            self.btn_apply_update.setVisible(False)
            self.btn_browser_dl.setVisible(False)
            self.btn_skip_ver.setVisible(False)
            self._render_default_changelog()
            self.txt_notes.append(
                f"<hr><p style='color:#DC2626;'><b>⚠️ 检查更新提示：</b>{result.message}<br>"
                "提示：您可在「系统设置 ➔ 版本管理与自动更新」中配置您自己的 GitHub / Gitee 仓库或服务器地址。</p>"
            )
            return

        manifest = result.manifest
        if manifest and manifest.hot_keywords:
            added = self.controller.apply_hot_keywords_from_manifest(manifest)
            if added > 0:
                self.lbl_status_sub.setText(f"{result.message}（已自动热更新 {added} 条识别词库！）")

        if result.has_update and manifest is not None:
            size_mb = f"{manifest.file_size / (1024 * 1024):.1f} MB" if manifest.file_size > 0 else "未知大小"
            sha_str = manifest.sha256[:24] + "..." if manifest.sha256 else "未提供 (直接替换)"
            notes_html = (manifest.release_notes or "暂无详细说明").replace("\n", "<br>")
            self.txt_notes.setHtml(
                f"<h3 style='color:#15803D;'>🎉 发现新版本 v{manifest.version}！(当前版本 v{result.current_version})</h3>"
                f"<p>📅 <b>发布日期：</b>{manifest.release_date} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"📦 <b>安装包大小：</b>{size_mb} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"🔒 <b>SHA256 校验：</b><code>{sha_str}</code></p>"
                f"<hr><h4 style='color:#1E3A8A;'>✨ 本次更新内容：</h4>"
                f"<div style='background:#F8FAFC;padding:10px;border-radius:8px;border:1px solid #E2E8F0;'>{notes_html}</div>"
                f"<p style='color:#64748B;font-size:12px;margin-top:10px;'>"
                f"💡 <b>数据安全保障：</b>您的所有客户档案、订单与配置均独立保存在 Windows 系统用户目录 "
                f"(<code>%LOCALAPPDATA%\\LotteryRiskPro\\data</code>)，自动升级替换 <code>.exe</code> 绝不会丢失任何数据！</p>"
            )
            self.btn_apply_update.setVisible(bool(manifest.download_url))
            self.btn_browser_dl.setVisible(bool(manifest.download_url))
            self.btn_skip_ver.setVisible(not manifest.force_update)
        else:
            self.btn_apply_update.setVisible(False)
            self.btn_browser_dl.setVisible(False)
            self.btn_skip_ver.setVisible(False)
            self._render_default_changelog()
            self.txt_notes.append(
                f"<hr><p style='color:#15803D;'><b>✅ {result.message}</b></p>"
            )

    def _on_skip_version(self) -> None:
        if self._check_result and self._check_result.manifest:
            ver = self._check_result.manifest.version
            cfg = self.controller.app_config
            cfg.skipped_version = ver
            self.controller.save_app_config(cfg)
            QMessageBox.information(self, "已跳过该版本", f"已设置跳过 v{ver} 的自动提醒。")
            self.close()

    def _on_open_browser_download(self) -> None:
        if self._check_result and self._check_result.manifest and self._check_result.manifest.download_url:
            url = AutoUpdateService.apply_mirror_prefix(
                self._check_result.manifest.download_url,
                self.controller.app_config.update_mirror_prefix,
            )
            QDesktopServices.openUrl(QUrl(url))

    def _on_start_download_update(self) -> None:
        if not self._check_result or not self._check_result.manifest:
            return
        manifest = self._check_result.manifest
        tmp_exe = Path(tempfile.gettempdir()) / f"LotteryRiskPro_update_v{manifest.version}.exe"

        self.btn_apply_update.setEnabled(False)
        self.btn_check_now.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status_sub.setText(f"正在下载新版本 v{manifest.version} 并执行 SHA256 完整性校验...")

        self._dl_worker = UpdateDownloadWorker(
            manifest=manifest,
            dest_path=tmp_exe,
            mirror_prefix=self.controller.app_config.update_mirror_prefix,
            parent=self,
        )
        self._dl_worker.progress_changed.connect(self._on_download_progress)
        self._dl_worker.download_succeeded.connect(self._on_download_succeeded)
        self._dl_worker.download_failed.connect(self._on_download_failed)
        self._dl_worker.start()

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = min(100, int(downloaded * 100 / total))
            self.progress_bar.setValue(pct)
            self.lbl_status_sub.setText(
                f"正在下载更新包：{downloaded / (1024 * 1024):.1f} MB / {total / (1024 * 1024):.1f} MB ({pct}%)"
            )
        else:
            self.progress_bar.setRange(0, 0)
            self.lbl_status_sub.setText(f"正在下载更新包：已下载 {downloaded / (1024 * 1024):.1f} MB...")

    def _on_download_succeeded(self, saved_path_str: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.btn_apply_update.setEnabled(True)
        self.btn_check_now.setEnabled(True)
        downloaded_exe = Path(saved_path_str)

        if getattr(sys, "frozen", False):
            reply = QMessageBox.question(
                self,
                "下载与 SHA256 校验成功",
                "新版安装包已下载并通过 SHA256 安全校验！\n\n"
                "是否立即自动替换旧版 .exe 并重新启动新版本？\n"
                "（您的所有客户档案与订单数据均保存在系统 AppData 目录，100% 安全保留）",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                if AutoUpdateService.trigger_self_update_and_restart(downloaded_exe):
                    sys.exit(0)
        else:
            QMessageBox.information(
                self,
                "更新包下载校验完成",
                f"新版安装包已下载并通过 SHA256 校验，保存位置：\n{downloaded_exe}\n\n"
                f"（当前为 Python 源码调试环境，打包后的 .exe 环境下将自动执行无缝自替换重启）",
            )

    def _on_download_failed(self, err_msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.btn_apply_update.setEnabled(True)
        self.btn_check_now.setEnabled(True)
        self.lbl_status_sub.setText(f"下载失败：{err_msg}")
        QMessageBox.warning(
            self,
            "自动下载更新失败",
            f"下载或校验新版本安装包时发生错误：\n{err_msg}\n\n"
            f"您可尝试配置「GitHub 下载加速镜像前缀」或点击「🌐 浏览器直接下载」手动获取。",
        )
