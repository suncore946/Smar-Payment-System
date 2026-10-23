"""
PyQt5 前端 UI 集成测试 (test_ui_integration.py)
验证主窗口、五大核心标签页、主题切换、微信解析入库、吃码反推与开奖算账完整交互闭环。
"""

from __future__ import annotations
from pathlib import Path
from PyQt5.QtGui import QKeySequence
from src.domain.models import SHORTCUT_DEFINITIONS
from src.services.app_controller import ApplicationController
from src.services.update_service import AutoUpdateService, ReleaseManifest
from src.ui.icon_manager import CartoonIconManager
from src.ui.main_window import MainWindow
from src.ui.update_dialog import UpdateDialog
from src.version import APP_VERSION, is_newer_version


def test_cartoon_icon_suite_completeness(qapp) -> None:
    """验证全套卡通图标（主Icon、6大导航Tab、快捷键图标、12生肖头像、3色波球、操作按钮）均可无损渲染"""
    keys = [
        "app_icon",
        "tab_dashboard",
        "tab_wechat",
        "tab_eat_risk",
        "tab_settlement",
        "tab_settings",
        "tab_help",
        "tab_history",
        "act_keyboard",
        "act_update",
        "ball_red",
        "ball_blue",
        "ball_green",
        "zodiac_马",
        "zodiac_龙",
        "zodiac_兔",
    ]
    for k in keys:
        pm = CartoonIconManager.render_pixmap(k, 64)
        assert not pm.isNull() and pm.width() == 64 and pm.height() == 64


def test_main_window_and_all_tabs_end_to_end(qapp, controller: ApplicationController) -> None:
    window = MainWindow(controller)
    window.show()
    qapp.processEvents()

    # 1. 验证七大核心标签页（含历史回看、设置页与使用说明页）齐全
    assert window.tabs.count() == 7
    assert window.tabs.indexOf(window.history_review_tab) == 4

    # 2. 在 Tab 2 (微信智能收单) 输入聊天文本并识别入库
    window.tabs.setCurrentIndex(1)
    qapp.processEvents()
    window.smart_entry_tab.txt_chat_input.setPlainText("马龙各100\n06,08各50")
    window.smart_entry_tab.run_parse()
    assert window.smart_entry_tab.tbl_parsed_preview.rowCount() == 3

    orders_before = len(controller.order_repo.list_orders(controller.current_region))
    window.smart_entry_tab.confirm_add_to_ledger()
    qapp.processEvents()
    orders_after = len(controller.order_repo.list_orders(controller.current_region))
    assert orders_after == orders_before + 1

    # 3. 切换到 Tab 3 (吃码上报) 执行按比例吃码
    window.tabs.setCurrentIndex(2)
    qapp.processEvents()
    window.eat_report_tab.spin_percent.setValue(40.0)
    window.eat_report_tab._on_apply_pct_eat()
    qapp.processEvents()
    assert window.eat_report_tab.risk_table.rowCount() == 49

    # 4. 切换到 Tab 4 (开奖算账) 选择 01 号特码对奖
    window.tabs.setCurrentIndex(3)
    qapp.processEvents()
    idx_01 = window.settlement_tab.cmb_winning_num.findData(1)
    window.settlement_tab.cmb_winning_num.setCurrentIndex(idx_01)
    window.settlement_tab._on_run_settlement()
    qapp.processEvents()
    assert window.settlement_tab.order_table.rowCount() == orders_after

    # 5. 切换到系统设置中心并测试暗色/亮色主题切换
    window.tabs.setCurrentWidget(window.settings_tab)
    qapp.processEvents()
    window._on_toggle_theme()
    qapp.processEvents()
    assert controller.app_config.theme_mode == "dark"

    # 6. 切换到使用说明与快捷键指南并验证语法表与快捷键速查表
    window.tabs.setCurrentWidget(window.help_guide_tab)
    qapp.processEvents()
    assert window.help_guide_tab.syntax_table.rowCount() == 14
    assert window.help_guide_tab.shortcut_table.rowCount() == len(SHORTCUT_DEFINITIONS)

    window.close()


def test_shortcuts_and_help_guide_interaction(qapp, controller: ApplicationController) -> None:
    """验证全局快捷键触发、使用说明互动试玩跳转以及自定义快捷键持久化"""
    window = MainWindow(controller)
    window.show()
    qapp.processEvents()

    # 1. 触发「打开使用说明」快捷键 (switch_tab_6 -> F1)
    assert window.trigger_shortcut_action("switch_tab_6") is True
    assert window.tabs.currentWidget() == window.help_guide_tab

    # 2. 从使用说明页点击「一键填入试玩」跳转到微信智能收单台并自动解析
    sample_txt = window.help_guide_tab.INTERACTIVE_SAMPLES[0][2]
    window.help_guide_tab.try_wechat_sample_requested.emit(sample_txt)
    qapp.processEvents()
    assert window.tabs.currentWidget() == window.smart_entry_tab
    assert window.smart_entry_tab.tbl_parsed_preview.rowCount() == 8

    # 3. 触发「识别结果转负数」与「清空输入框」快捷键
    assert window.trigger_shortcut_action("negate_parsed") is True
    assert window.smart_entry_tab._parsed_items[0].per_number_amount < 0
    assert window.trigger_shortcut_action("clear_wechat_input") is True
    assert window.smart_entry_tab.tbl_parsed_preview.rowCount() == 0

    # 4. 从使用说明页点击「前往自定义修改快捷键」跳转到设置页快捷键子页
    window.help_guide_tab.open_shortcut_settings_requested.emit()
    qapp.processEvents()
    assert window.tabs.currentWidget() == window.settings_tab
    assert window.settings_tab.sub_tabs.currentIndex() == 1

    # 5. 修改「立即识别微信报单文本」快捷键为 Ctrl+R 并验证持久化与同步
    editor = window.settings_tab._shortcut_editors["parse_wechat"]
    editor.setKeySequence(QKeySequence("Ctrl+R"))
    cfg = controller.app_config
    cfg.shortcuts["parse_wechat"] = editor.keySequence().toString()
    controller.save_app_config(cfg)
    window._on_settings_updated()
    qapp.processEvents()

    reloaded_cfg = controller.config_repo.load_app_config()
    assert reloaded_cfg.get_shortcut("parse_wechat") == "Ctrl+R"
    assert "Ctrl+R" in window.smart_entry_tab.btn_parse_now.text()

    # 6. 测试修改/更正客户名
    old_c_name = controller.get_active_client().name
    assert controller.client_repo.rename_client(controller.current_region, old_c_name, "尊贵VIP999") is True
    controller.set_active_client("尊贵VIP999", controller.current_region)
    window.refresh_all()
    qapp.processEvents()
    assert controller.get_active_client().name == "尊贵VIP999"
    assert "尊贵VIP999" in window.cmb_active_client.currentText()

    window.close()


def test_version_management_and_auto_update_workflow(
    tmp_path: Path, qapp, controller: ApplicationController
) -> None:
    """验证版本比较、GitHub/Gitee API 解析、本地/远端 version.json 校验下载、热词库更新及自更新脚本生成"""
    # 1. 语义化版本对比测试
    assert is_newer_version("9.9.9", APP_VERSION) is True
    assert is_newer_version("1.0.0", APP_VERSION) is False
    assert is_newer_version(APP_VERSION, APP_VERSION) is False

    # 2. GitHub / Gitee Releases API 地址解析测试
    gh_ep = AutoUpdateService.resolve_check_endpoint("github_api", "demo-user/lottery-pro")
    assert gh_ep == "https://api.github.com/repos/demo-user/lottery-pro/releases/latest"
    gt_ep = AutoUpdateService.resolve_check_endpoint("gitee_api", "https://gitee.com/demo-user/lottery-pro")
    assert gt_ep == "https://gitee.com/api/v5/repos/demo-user/lottery-pro/releases/latest"

    # 3. 模拟构建一个新版 dummy.exe 并生成 version.json 清单
    dummy_new_exe = tmp_path / "NewRelease.exe"
    dummy_new_exe.write_bytes(b"MZ-DUMMY-NEW-EXE-BINARY-CONTENT-V999")
    manifest_json = tmp_path / "version.json"

    manifest = AutoUpdateService.generate_version_manifest_file(
        exe_path=dummy_new_exe,
        output_json_path=manifest_json,
        download_url=str(dummy_new_exe),
    )
    # 将模拟远端清单版本号设为 9.9.0 并附带一条增量热更新词条
    import json
    raw_dict = json.loads(manifest_json.read_text(encoding="utf-8"))
    raw_dict["version"] = "9.9.0"
    raw_dict["hot_keywords"] = {"各字": ["热更新测试各码"]}
    manifest_json.write_text(json.dumps(raw_dict, ensure_ascii=False), encoding="utf-8")

    # 4. 配置 Controller 指向该 version.json 并执行检查更新
    cfg = controller.app_config
    cfg.update_source_mode = "github_or_json"
    cfg.update_repo_or_url = str(manifest_json)
    controller.save_app_config(cfg)

    check_res = controller.check_for_updates()
    assert check_res.success is True
    assert check_res.has_update is True
    assert check_res.latest_version == "9.9.0"
    assert check_res.manifest is not None

    # 5. 验证 UpdateDialog 渲染与热更新词库自动合并
    dlg = UpdateDialog(controller, initial_result=check_res)
    qapp.processEvents()
    assert "热更新测试各码" in controller.keyword_repo.get_keywords("各字")
    dlg.close()

    # 6. 验证带 SHA256 校验的安装包流式下载与 Windows 自替换批处理脚本生成
    dl_target = tmp_path / "downloaded_v990.exe"
    verified_path = AutoUpdateService.download_and_verify_release(
        manifest=check_res.manifest,
        dest_path=dl_target,
    )
    assert verified_path.exists()
    assert AutoUpdateService.compute_file_sha256(verified_path) == check_res.manifest.sha256

    bat_path = AutoUpdateService.create_windows_self_update_script(
        current_exe=tmp_path / "OldApp.exe",
        downloaded_exe=verified_path,
    )
    assert bat_path.exists()
    assert "move /y" in bat_path.read_text(encoding="utf-8")
