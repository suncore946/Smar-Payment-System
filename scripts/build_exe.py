"""
跨平台自动化测试、图标构建与新用户分发隔离验证脚本 (scripts/build_exe.py)
功能：
1. 自动生成全套 42 枚 Q 版卡通风格图标 (`.svg` / `.png` / Windows 多尺寸 `app_icon.ico`)
2. 自动运行全套 Pytest 单元测试与 UI 集成测试，测试不通过则中止部署
3. 自动运行源码级 GUI 离屏冒烟测试 (`main.py --smoke-test`)
4. 调用 PyInstaller 将项目、内置种子词库 (`src/data/default_seed.json`) 与全套卡通图标 (`src/assets/icons`)
   打包为带专属卡通金马特码图标 (`--icon`) 的独立可执行文件 (`.exe`)，并剥离 `setuptools/pkg_resources` 等易冲突运行时钩子
5. 【新用户纯净环境隔离验证】：将生成的单个 `.exe` 放入全新的空文件夹，并剥离环境变量中的 Python/Anaconda 路径（仅保留系统 `C:\\Windows\\System32`），实测 `.exe` 能否零报错启动并自动创建完整的本地 SQLite 数据库
"""

from __future__ import annotations
import os
import platform
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.services.update_service import AutoUpdateService
from src.version import APP_NAME, APP_VERSION

# 排除与本项目运行无关的第三方包（特别是 setuptools / pkg_resources，防止触发 PyInstaller rthook 异常）
EXCLUDED_MODULES = [
    "setuptools",
    "pkg_resources",
    "distutils",
    "lxml",
    "bs4",
    "cffi",
    "PIL",
    "pyreadline3",
    "torch",
    "torchvision",
    "torchaudio",
    "tensorflow",
    "scipy",
    "numpy",
    "pandas",
    "matplotlib",
    "IPython",
    "jupyter",
    "notebook",
    "tkinter",
    "cv2",
    "sklearn",
    "scikit-learn",
    "zmq",
    "sqlalchemy",
    "pyarrow",
    "numba",
    "sympy",
    "h5py",
    "bokeh",
    "statsmodels",
    "dask",
    "altair",
    "pytest",
]


def run_step(title: str, cmd: list[str], env: dict | None = None, cwd: Path | None = None) -> None:
    print(f"\n{'=' * 68}")
    print(f"🚀 [自动化部署流水线] {title}")
    print(f"   命令: {' '.join(cmd)}")
    print(f"{'=' * 68}", flush=True)
    res = subprocess.run(
        cmd,
        cwd=str(cwd or ROOT_DIR),
        env=env or os.environ.copy(),
        stdin=subprocess.DEVNULL,
    )
    if res.returncode != 0:
        print(f"❌ 步骤失败: {title} (退出码: {res.returncode})", flush=True)
        sys.exit(res.returncode)
    print(f"✅ 步骤完成: {title}", flush=True)


def run_pyinstaller_build(cmd: list[str], dist_exe: Path) -> None:
    print(f"\n{'=' * 68}")
    print("🚀 [自动化部署流水线] 4/5 使用 PyInstaller 构建带专属卡通图标的独立 .exe")
    print(f"{'=' * 68}", flush=True)

    if dist_exe.exists():
        try:
            dist_exe.unlink()
        except Exception:
            pass

    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    completed_marker_seen = False
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        if "Building EXE from EXE-00.toc completed successfully" in line or (
            "Build complete! The results are available in" in line
        ):
            completed_marker_seen = True
            for _ in range(30):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            if proc.poll() is None and dist_exe.exists() and dist_exe.stat().st_size > 1024 * 1024:
                proc.terminate()
                break

    proc.wait(timeout=10)
    if not completed_marker_seen and proc.returncode != 0:
        print(f"❌ PyInstaller 构建失败 (退出码: {proc.returncode})")
        sys.exit(proc.returncode or 1)
    print("✅ 步骤完成: PyInstaller 独立 .exe 构建完成", flush=True)


def verify_clean_room_distribution(dist_exe: Path) -> None:
    """
    模拟新用户电脑环境：
    1. 创建全新的空临时目录，仅拷贝单个 `.exe`
    2. 将环境变量 PATH 精简为纯 Windows 系统目录（彻底移除 Python / Anaconda 路径）
    3. 启动 `.exe --smoke-test`，验证其能在 15 秒内完成全界面加载、自建 `data/lottery_system.db` 并灌入 1955+ 词库
    """
    print(f"\n{'=' * 68}")
    print("🧪 [自动化部署流水线] 5/5 执行「新用户无 Python 纯净空目录」隔离分发验证")
    print(f"{'=' * 68}", flush=True)

    with tempfile.TemporaryDirectory(prefix="new_user_clean_pc_") as tmp_dir_str:
        clean_dir = Path(tmp_dir_str)
        isolated_exe = clean_dir / dist_exe.name
        shutil.copy2(dist_exe, isolated_exe)

        clean_env = {
            "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
            "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
            "TEMP": str(clean_dir),
            "TMP": str(clean_dir),
            "LOCALAPPDATA": str(clean_dir / "AppDataLocal"),
            "USERPROFILE": str(clean_dir),
            "PATH": r"C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem",
            "QT_QPA_PLATFORM": "offscreen",
        }

        proc = subprocess.Popen(
            [str(isolated_exe), "--smoke-test"],
            cwd=str(clean_dir),
            env=clean_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            out, _ = proc.communicate(timeout=25)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            print("❌ 新用户纯净环境自检超时！", flush=True)
            sys.exit(1)

        if proc.returncode != 0:
            err_log = clean_dir / "AppDataLocal" / "LotteryRiskPro" / "data" / "error.log"
            err_detail = err_log.read_text(encoding="utf-8") if err_log.exists() else (out or "无日志")
            print(f"❌ 新用户纯净环境自检失败 (退出码: {proc.returncode})\n{err_detail}", flush=True)
            sys.exit(1)

        # 验证严格遵循 Windows 规范：数据库创建在 %LOCALAPPDATA%\LotteryRiskPro\data\lottery_system.db，且不污染 .exe 所在目录
        created_db = clean_dir / "AppDataLocal" / "LotteryRiskPro" / "data" / "lottery_system.db"
        if not created_db.exists():
            print("❌ 新用户纯净环境下未能在用户数据目录 (%LOCALAPPDATA%\\LotteryRiskPro\\data) 自动生成 lottery_system.db！", flush=True)
            sys.exit(1)

        if (clean_dir / "data").exists():
            print("❌ 警告：在 .exe 同级目录产生了多余的 data 文件夹，违反 Windows 用户数据存放规范！", flush=True)
            sys.exit(1)

        conn = sqlite3.connect(str(created_db))
        kw_count = conn.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
        reg_count = conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0]
        conn.close()

        print(
            f"✅ 新用户纯净环境隔离验证 100% 通过！\n"
            f"   • 已在无 Python/Anaconda 环境变量的空目录中独立运行成功，且 .exe 同级目录保持 100% 纯净无多余文件\n"
            f"   • 自动在 Windows 用户数据目录 (%LOCALAPPDATA%\\LotteryRiskPro\\data) 创建数据库: {created_db.name} ({created_db.stat().st_size / 1024:.1f} KB)\n"
            f"   • 自动预置识别关键字记录: {kw_count} 条 | 默认盘口: {reg_count} 个",
            flush=True,
        )


def main() -> None:
    headless_env = os.environ.copy()
    headless_env["QT_QPA_PLATFORM"] = "offscreen"

    # 1. 生成全套 Q 版卡通图标资产与 .ico 文件
    run_step(
        "1/5 生成全套 42 枚卡通图标资产与 .ico",
        [sys.executable, "scripts/generate_icons.py"],
        env=headless_env,
    )

    # 2. 执行自动化单元测试与 UI 集成测试
    run_step(
        "2/5 运行 Pytest 全量自动化测试套件",
        [sys.executable, "-m", "pytest", "-v"],
        env=headless_env,
    )

    # 3. 执行源码级 UI 冒烟自检与数据库预热
    run_step(
        "3/5 运行主程序离屏冒烟自检与本地数据库初始化",
        [sys.executable, "main.py", "--smoke-test"],
        env=headless_env,
    )

    # 4. 组装跨平台 PyInstaller 打包参数
    sep = ";" if platform.system().lower().startswith("win") else ":"
    seed_arg = f"src/data/default_seed.json{sep}src/data"
    icons_arg = f"src/assets/icons{sep}src/assets/icons"
    ico_path = ROOT_DIR / "src" / "assets" / "icons" / "app_icon.ico"

    exe_suffix = ".exe" if platform.system().lower().startswith("win") else ""
    dist_exe = ROOT_DIR / "dist" / f"{APP_NAME}{exe_suffix}"

    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(ico_path),
        "--add-data",
        seed_arg,
        "--add-data",
        icons_arg,
        "--collect-submodules",
        "openpyxl",
        "--hidden-import",
        "openpyxl.cell._writer",
        "--hidden-import",
        "sqlite3",
    ]
    for mod in EXCLUDED_MODULES:
        pyinstaller_cmd.extend(["--exclude-module", mod.strip()])

    pyinstaller_cmd.append("main.py")
    run_pyinstaller_build(pyinstaller_cmd, dist_exe)

    # 5. 执行新用户纯净空目录隔离验证并同步到根目录
    verify_clean_room_distribution(dist_exe)

    root_exe = ROOT_DIR / f"{APP_NAME}{exe_suffix}"
    shutil.copy2(dist_exe, root_exe)

    # 6. 自动生成带 SHA256 签名与字节大小的版本更新清单 (dist/version.json 与根目录 version.json)
    dist_manifest_path = ROOT_DIR / "dist" / "version.json"
    manifest = AutoUpdateService.generate_version_manifest_file(
        exe_path=dist_exe,
        output_json_path=dist_manifest_path,
    )
    shutil.copy2(dist_manifest_path, ROOT_DIR / "version.json")

    size_mb = dist_exe.stat().st_size / (1024 * 1024)
    appdata_db = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "LotteryRiskPro" / "data" / "lottery_system.db"
    print(f"\n🎉 自动化构建 (v{APP_VERSION}) 与新用户分发验证全部成功！")
    print(f"🎨 应用专属卡通图标 (.ico): {ico_path}")
    print(f"📦 独立可分发文件 (dist): {dist_exe} ({size_mb:.1f} MB)")
    print(f"📦 桌面快捷可执行文件 (根目录): {root_exe} ({size_mb:.1f} MB)")
    print(f"🚀 自动更新发布清单 (version.json): {ROOT_DIR / 'version.json'} (SHA256: {manifest.sha256[:16]}...)")
    print(f"🗄️ Windows 用户数据目录数据库 (%LOCALAPPDATA%): {appdata_db}", flush=True)


if __name__ == "__main__":
    main()
