"""
特码智能收单与吃码风控系统 Pro v2.0 — 应用程序主入口 (main.py)
针对新用户分发场景与 Windows 用户习惯进行了全方位加固：
1. 遵循 Windows 标准用户数据存储规范：默认将本地数据库与配置存放在系统用户数据目录
   `%LOCALAPPDATA%\\LotteryRiskPro\\data\\lottery_system.db`（macOS/Linux 对应各自标准 User Data 目录），
   不污染桌面或 `.exe` 所在目录，且直接替换升级 `.exe` 文件时历史数据与配置 100% 自动保留。
2. Qt 插件路径与系统字库自愈：自动定位打包内嵌的 Qt platforms/iconengines/imageformats 插件，缺失字体自动降级。
3. 数据库与配置自愈：若数据库文件首次创建或意外损坏，自动重建并灌入内置 1,955+ 词库与默认盘口配置。
4. `--smoke-test` 自动化冒烟测试模式（用于分发前纯净环境隔离自检）。
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
import traceback

# 在导入 QtWidgets 之前检查 --smoke-test 参数，确保无头离屏模式优先就绪
if "--smoke-test" in sys.argv and "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"


def _configure_bundled_qt_plugin_paths() -> None:
    """确保在任何没有安装 Python/Qt 的纯净新用户电脑上都能正确加载内置 Qt 平台插件"""
    if hasattr(sys, "_MEIPASS"):
        meipass = Path(getattr(sys, "_MEIPASS"))
        for candidate in [
            meipass / "PyQt5" / "Qt5" / "plugins",
            meipass / "PyQt5" / "Qt" / "plugins",
            meipass / "qt5_plugins",
        ]:
            if candidate.exists():
                os.environ["QT_PLUGIN_PATH"] = str(candidate)
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(candidate / "platforms")
                break


_configure_bundled_qt_plugin_paths()


def get_app_base_dir() -> Path:
    """获取应用程序所在根目录（兼容 PyInstaller 打包后的 exe 目录与源码运行目录）"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resolve_writable_db_path(custom_db_path: str = "") -> Path:
    """
    遵循 Windows / 跨平台操作系统用户数据习惯解析本地 SQLite 数据库路径：
    1. 若显式指定了 `--db-path`，使用指定路径；
    2. 默认统一存放在系统当前用户数据目录：
       - Windows: `%LOCALAPPDATA%\\LotteryRiskPro\\data\\lottery_system.db`
       - macOS: `~/Library/Application Support/LotteryRiskPro/data/lottery_system.db`
       - Linux: `~/.local/share/LotteryRiskPro/data/lottery_system.db`
       这样无论用户把 `.exe` 放在桌面、下载目录还是 `C:\\Program Files`，都不会在当前目录产生多余文件夹，
       且随意移动或更新 `.exe` 时用户数据永久保留。
    """
    if custom_db_path:
        p = Path(custom_db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else (Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        root = Path(xdg) if xdg else (Path.home() / ".local" / "share")

    user_data_dir = root / "LotteryRiskPro" / "data"
    try:
        user_data_dir.mkdir(parents=True, exist_ok=True)
        return user_data_dir / "lottery_system.db"
    except Exception:
        fallback_dir = get_app_base_dir() / "data"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / "lottery_system.db"


def write_error_log(err_msg: str) -> None:
    """将运行异常记录到本地日志，便于排查且不影响主流程"""
    try:
        log_path = resolve_writable_db_path().parent / "error.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(err_msg + "\n" + ("-" * 60) + "\n")
    except Exception:
        pass


try:
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from src.services.app_controller import ApplicationController
    from src.ui.icon_manager import CartoonIconManager
    from src.ui.main_window import MainWindow
except Exception:
    _boot_err = traceback.format_exc()
    write_error_log(_boot_err)
    if sys.stderr is not None:
        try:
            sys.stderr.write(_boot_err)
        except Exception:
            pass
    os._exit(1)


def install_global_exception_handler(smoke_test: bool = False) -> None:
    """安装全局未捕获异常处理器，防止界面静默闪退并提供友好提示"""

    def _excepthook(exc_type, exc_value, exc_tb):
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        write_error_log(err_msg)
        if sys.stderr is not None:
            try:
                sys.stderr.write(err_msg)
            except Exception:
                pass
        if smoke_test:
            os._exit(1)
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None,
                "系统运行异常提醒",
                f"操作过程中遇到意外错误（您的数据已安全保存在本地数据库）：\n\n{exc_value}",
            )

    sys.excepthook = _excepthook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="特码智能收单与吃码风控系统 Pro")
    parser.add_argument(
        "--db-path",
        type=str,
        default="",
        help="自定义本地 SQLite 数据库文件路径",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="启动 UI 冒烟自检后自动退出（供自动化部署与测试验证使用）",
    )
    args, qt_args = parser.parse_known_args(argv)

    if args.smoke_test and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    install_global_exception_handler(smoke_test=args.smoke_test)

    # 启用跨平台 High-DPI 缩放支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("特码智能收单与吃码风控系统 Pro")
    app.setOrganizationName("LotteryProStudio")
    CartoonIconManager.ensure_fonts_loaded()
    app.setWindowIcon(CartoonIconManager.get_icon("app_icon"))

    db_path = resolve_writable_db_path(args.db_path)
    controller = ApplicationController(db_path=db_path, auto_seed=True)
    window = MainWindow(controller)
    window.show()

    if args.smoke_test:
        def _run_smoke_cycle():
            try:
                for idx in range(window.tabs.count()):
                    window.tabs.setCurrentIndex(idx)
                    app.processEvents()
                window.close()
                app.processEvents()
            except Exception:
                write_error_log(traceback.format_exc())
                os._exit(1)
            os._exit(0)

        QTimer.singleShot(100, _run_smoke_cycle)

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
