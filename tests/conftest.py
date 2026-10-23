"""
Pytest 全局测试夹具配置 (conftest.py)
提供内存数据库 (:memory:) 控制器与带完整种子数据的测试环境。
"""

from __future__ import annotations
import os
from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt5.QtWidgets import QApplication
from src.services.app_controller import ApplicationController

# 确保测试在无头/离屏模式下也能稳定运行 PyQt5 组件
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """全局单例 QApplication 夹具"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["pytest_app"])
    return app


@pytest.fixture()
def controller() -> ApplicationController:
    """使用内存 SQLite 数据库并自动加载默认词库与种子数据的控制器"""
    ctrl = ApplicationController(db_path=":memory:", auto_seed=True)
    return ctrl


@pytest.fixture()
def clean_controller() -> ApplicationController:
    """使用内存 SQLite 数据库且清空盘口订单的干净控制器（保留 1,955+ 识别关键字词库）"""
    ctrl = ApplicationController(db_path=":memory:", auto_seed=True)
    for r in ctrl.region_repo.list_regions():
        ctrl.settlement_service.clear_region_all_data(r.name)
    return ctrl
