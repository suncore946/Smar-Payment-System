"""
系统主窗口 (MainWindow)
采用面向对象组件化设计，整合：
1. 顶部全局导航栏（盘口切换、当前收单客户切换、本命年生肖徽章、Excel 导入/导出、暗黑/亮色主题切换）
2. 五大核心业务工作台标签页（主控看板、智能收单、吃码上报、开奖算账、自定义配置与词库）
3. 系统剪贴板实时监听（支持微信复制即自动识别）与底部实时状态栏
"""

from __future__ import annotations
from pathlib import Path
from typing import Callable, Dict, List
from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from src.domain.models import ClientProfile, RegionConfig, SHORTCUT_DEFINITIONS
from src.services.app_controller import ApplicationController
from src.ui.dashboard_tab import DashboardTab
from src.ui.eat_report_tab import EatReportTab
from src.ui.help_guide_tab import HelpGuideTab
from src.ui.history_review_tab import HistoryReviewTab
from src.ui.icon_manager import CartoonIconManager
from src.ui.settlement_tab import SettlementTab
from src.ui.settings_tab import SettingsTab
from src.ui.smart_entry_tab import SmartEntryTab
from src.ui.styles import ThemeManager
from src.ui.update_dialog import UpdateCheckWorker, UpdateDialog
from src.version import APP_VERSION


class MainWindow(QMainWindow):
    """六合彩/特码智能收单、吃码风控与结算系统主窗口"""

    def __init__(self, controller: ApplicationController) -> None:
        super().__init__()
        self.controller = controller
        self._last_clipboard_text: str = ""
        self._updating_header: bool = False
        self._active_shortcuts: List[QShortcut] = []
        self._shortcut_handlers: Dict[str, Callable[[], None]] = {}
        self._startup_update_worker: UpdateCheckWorker | None = None

        self.setWindowTitle(
            f"特码智能收单与吃码风控系统 Pro v{APP_VERSION} — [农历{self.controller.app_config.base_zodiac}年 · 本地数据库版]"
        )
        self.setWindowIcon(CartoonIconManager.get_icon("app_icon"))
        self.resize(1560, 920)
        self.setMinimumSize(1280, 760)

        self._init_ui()
        self._init_shortcut_handlers()
        self._rebuild_global_shortcuts()
        self._apply_theme()
        self._setup_clipboard_listener()
        self._setup_auto_backup_timer()
        self.refresh_all()

        if self.controller.app_config.auto_check_update_on_startup:
            QTimer.singleShot(2500, self._run_silent_startup_update_check)

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ================= 1. 顶部全局导航与快捷控制栏 =================
        header_bar = QFrame()
        header_bar.setObjectName("TopHeaderBar")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(10)

        self.lbl_logo_icon = QLabel()
        self.lbl_logo_icon.setPixmap(CartoonIconManager.render_pixmap("app_icon", 36))
        header_layout.addWidget(self.lbl_logo_icon)

        self.lbl_app_title = QLabel("特码智能收单与风控工作站 Pro")
        self.lbl_app_title.setObjectName("AppTitleLabel")
        header_layout.addWidget(self.lbl_app_title)

        self.lbl_zodiac_icon = QLabel()
        self.lbl_zodiac_icon.setPixmap(
            CartoonIconManager.render_pixmap(f"zodiac_{self.controller.app_config.base_zodiac}", 28)
        )
        header_layout.addWidget(self.lbl_zodiac_icon)

        self.lbl_zodiac_badge = QLabel(f"本命年：{self.controller.app_config.base_zodiac}年")
        self.lbl_zodiac_badge.setObjectName("HeaderBadge")
        header_layout.addWidget(self.lbl_zodiac_badge)

        header_layout.addSpacing(6)

        # 盘口切换器
        lbl_reg = QLabel("当前盘口:")
        lbl_reg.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(lbl_reg)

        self.cmb_region = QComboBox()
        self.cmb_region.setMinimumWidth(115)
        self.cmb_region.currentTextChanged.connect(self._on_region_changed)
        header_layout.addWidget(self.cmb_region)

        btn_add_region = QPushButton("新增盘口")
        btn_add_region.setIcon(CartoonIconManager.get_icon("act_plus"))
        btn_add_region.setToolTip("新增自定义盘口地区")
        btn_add_region.clicked.connect(self._on_add_region)
        header_layout.addWidget(btn_add_region)

        # 当前激活客户切换器
        lbl_cli = QLabel("当前收单客户:")
        lbl_cli.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(lbl_cli)

        self.cmb_active_client = QComboBox()
        self.cmb_active_client.setMinimumWidth(135)
        self.cmb_active_client.currentTextChanged.connect(self._on_active_client_changed)
        header_layout.addWidget(self.cmb_active_client)

        btn_quick_add_client = QPushButton("新增客户")
        btn_quick_add_client.setIcon(CartoonIconManager.get_icon("act_plus"))
        btn_quick_add_client.setToolTip("快速新增收单客户 (Ctrl+N)")
        btn_quick_add_client.clicked.connect(self._on_quick_add_client)
        header_layout.addWidget(btn_quick_add_client)

        btn_rename_client = QPushButton("修正客户名")
        btn_rename_client.setIcon(CartoonIconManager.get_icon("act_edit"))
        btn_rename_client.setToolTip("修改/修正当前收单客户名称，系统将自动同步更新所有历史订单与盘口关联")
        btn_rename_client.clicked.connect(self._on_rename_current_client)
        header_layout.addWidget(btn_rename_client)

        header_layout.addStretch()

        # Excel 导入与导出按钮
        btn_import_excel = QPushButton("导入 Excel 数据")
        btn_import_excel.setIcon(CartoonIconManager.get_icon("act_import_excel"))
        btn_import_excel.setObjectName("SuccessBtn")
        btn_import_excel.clicked.connect(self._on_import_excel)
        header_layout.addWidget(btn_import_excel)

        btn_export_excel = QPushButton("导出 Excel 报表")
        btn_export_excel.setIcon(CartoonIconManager.get_icon("act_export_excel"))
        btn_export_excel.setObjectName("WarningBtn")
        btn_export_excel.clicked.connect(self._on_export_excel)
        header_layout.addWidget(btn_export_excel)

        # 主题切换按钮
        self.btn_theme = QPushButton("暗色模式")
        self.btn_theme.setIcon(CartoonIconManager.get_icon("act_theme_dark"))
        self.btn_theme.clicked.connect(self._on_toggle_theme)
        header_layout.addWidget(self.btn_theme)

        # 快捷设置与使用说明按钮
        self.btn_quick_settings = QPushButton("系统设置")
        self.btn_quick_settings.setIcon(CartoonIconManager.get_icon("tab_settings"))
        self.btn_quick_settings.setToolTip("打开系统设置与快捷键配置中心")
        self.btn_quick_settings.clicked.connect(lambda: self.tabs.setCurrentWidget(self.settings_tab))
        header_layout.addWidget(self.btn_quick_settings)

        self.btn_quick_help = QPushButton("使用说明 (F1)")
        self.btn_quick_help.setIcon(CartoonIconManager.get_icon("tab_help"))
        self.btn_quick_help.setToolTip("打开图文使用教程、微信报单语法大全与快捷键指南")
        self.btn_quick_help.clicked.connect(lambda: self.tabs.setCurrentWidget(self.help_guide_tab))
        header_layout.addWidget(self.btn_quick_help)

        self.btn_check_update = QPushButton(f"v{APP_VERSION} 更新")
        self.btn_check_update.setIcon(CartoonIconManager.get_icon("act_update"))
        self.btn_check_update.setToolTip("查看版本更新日志或连接 Git/服务器检查新版本 (Ctrl+U)")
        self.btn_check_update.clicked.connect(self.open_update_dialog)
        header_layout.addWidget(self.btn_check_update)

        root_layout.addWidget(header_bar)

        # ================= 2. 核心工作台标签页 (6 Tabs) =================
        body_container = QWidget()
        body_layout = QVBoxLayout(body_container)
        body_layout.setContentsMargins(10, 8, 10, 6)
        body_layout.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(24, 24))
        self.dashboard_tab = DashboardTab(self.controller, on_data_changed=self.refresh_all, parent=self)
        self.smart_entry_tab = SmartEntryTab(self.controller, on_order_submitted=self.refresh_all, parent=self)
        self.eat_report_tab = EatReportTab(self.controller, parent=self)
        self.settlement_tab = SettlementTab(self.controller, parent=self)
        self.history_review_tab = HistoryReviewTab(self.controller, parent=self)
        self.settings_tab = SettingsTab(self.controller, parent=self)
        self.help_guide_tab = HelpGuideTab(self.controller, parent=self)

        self.eat_report_tab.data_changed.connect(self.refresh_all)
        self.settlement_tab.data_changed.connect(self.refresh_all)
        self.history_review_tab.data_changed.connect(self.refresh_all)
        self.settings_tab.config_changed.connect(self._on_settings_updated)
        self.help_guide_tab.navigate_tab_requested.connect(self.tabs.setCurrentIndex)
        self.help_guide_tab.open_shortcut_settings_requested.connect(self._open_shortcut_settings)
        self.help_guide_tab.try_wechat_sample_requested.connect(self._on_try_wechat_sample)

        self.tabs.addTab(
            self.dashboard_tab,
            CartoonIconManager.get_icon("tab_dashboard"),
            "主控看板与实时风控",
        )
        self.tabs.addTab(
            self.smart_entry_tab,
            CartoonIconManager.get_icon("tab_wechat"),
            "微信智能收单与极速录单",
        )
        self.tabs.addTab(
            self.eat_report_tab,
            CartoonIconManager.get_icon("tab_eat_risk"),
            "吃码上报与飞单风控",
        )
        self.tabs.addTab(
            self.settlement_tab,
            CartoonIconManager.get_icon("tab_settlement"),
            "订单明细与开奖算账",
        )
        self.tabs.addTab(
            self.history_review_tab,
            CartoonIconManager.get_icon("tab_history"),
            "历史日期回看与复盘",
        )
        self.tabs.addTab(
            self.settings_tab,
            CartoonIconManager.get_icon("tab_settings"),
            "系统设置与客户配置",
        )
        self.tabs.addTab(
            self.help_guide_tab,
            CartoonIconManager.get_icon("tab_help"),
            "使用说明与快捷键指南",
        )

        body_layout.addWidget(self.tabs, 1)
        root_layout.addWidget(body_container, 1)

        # ================= 3. 底部状态栏 =================
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status_info = QLabel("")
        self.status_bar.addPermanentWidget(self.lbl_status_info, 1)

    def _init_shortcut_handlers(self) -> None:
        """初始化全部 20 项可自定义快捷键对应的业务动作处理器"""
        self._shortcut_handlers = {
            "switch_tab_1": lambda: self.tabs.setCurrentWidget(self.dashboard_tab),
            "switch_tab_2": lambda: self.tabs.setCurrentWidget(self.smart_entry_tab),
            "switch_tab_3": lambda: self.tabs.setCurrentWidget(self.eat_report_tab),
            "switch_tab_4": lambda: self.tabs.setCurrentWidget(self.settlement_tab),
            "switch_tab_history": lambda: self.tabs.setCurrentWidget(self.history_review_tab),
            "switch_tab_5": lambda: self.tabs.setCurrentWidget(self.settings_tab),
            "switch_tab_6": lambda: self.tabs.setCurrentWidget(self.help_guide_tab),
            "parse_wechat": self._shortcut_parse_wechat,
            "submit_order": self._shortcut_submit_order,
            "paste_and_parse": self._shortcut_paste_and_parse,
            "clear_wechat_input": self._shortcut_clear_wechat,
            "negate_parsed": self._shortcut_negate_wechat,
            "focus_quick_input": self._shortcut_focus_quick_input,
            "copy_eat_report": self._shortcut_copy_eat_report,
            "run_settlement": self._shortcut_run_settlement,
            "copy_settlement_bill": self._shortcut_copy_settlement_bill,
            "quick_add_client": self._on_quick_add_client,
            "rename_current_client": self._on_rename_current_client,
            "export_excel": self._on_export_excel,
            "backup_database": self.settings_tab._on_backup_db,
            "toggle_theme": self._on_toggle_theme,
            "refresh_all": self.refresh_all,
            "check_update": self.open_update_dialog,
        }

    def _rebuild_global_shortcuts(self) -> None:
        """根据 AppConfig 中的用户自定义快捷键字典，动态绑定或重绑全局 QShortcut"""
        for sc in self._active_shortcuts:
            sc.setEnabled(False)
            sc.setParent(None)
        self._active_shortcuts.clear()

        cfg = self.controller.app_config
        for defn in SHORTCUT_DEFINITIONS:
            key_str = cfg.get_shortcut(defn.action_id).strip()
            handler = self._shortcut_handlers.get(defn.action_id)
            if not key_str or handler is None:
                continue
            sc = QShortcut(QKeySequence(key_str), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(handler)
            self._active_shortcuts.append(sc)

        help_key = cfg.get_shortcut("switch_tab_6")
        self.btn_quick_help.setText(f"使用说明 ({help_key})" if help_key else "使用说明")

    def trigger_shortcut_action(self, action_id: str) -> bool:
        """显式触发指定动作 ID 的快捷键行为（供自动化测试与程序调用）"""
        handler = self._shortcut_handlers.get(action_id)
        if handler is None:
            return False
        handler()
        return True

    def _shortcut_parse_wechat(self) -> None:
        self.tabs.setCurrentWidget(self.smart_entry_tab)
        self.smart_entry_tab.run_parse()

    def _shortcut_submit_order(self) -> None:
        self.tabs.setCurrentWidget(self.smart_entry_tab)
        self.smart_entry_tab.confirm_add_to_ledger()

    def _shortcut_paste_and_parse(self) -> None:
        self.tabs.setCurrentWidget(self.smart_entry_tab)
        self.smart_entry_tab.paste_and_parse()

    def _shortcut_clear_wechat(self) -> None:
        self.tabs.setCurrentWidget(self.smart_entry_tab)
        self.smart_entry_tab._on_clear_clicked()

    def _shortcut_negate_wechat(self) -> None:
        self.tabs.setCurrentWidget(self.smart_entry_tab)
        self.smart_entry_tab._on_negate_clicked()

    def _shortcut_focus_quick_input(self) -> None:
        self.tabs.setCurrentWidget(self.smart_entry_tab)
        self.smart_entry_tab.focus_quick_code_input()

    def _shortcut_copy_eat_report(self) -> None:
        self.tabs.setCurrentWidget(self.eat_report_tab)
        self.eat_report_tab._copy_specific_type("上报")

    def _shortcut_run_settlement(self) -> None:
        self.tabs.setCurrentWidget(self.settlement_tab)
        self.settlement_tab._on_run_settlement()

    def _shortcut_copy_settlement_bill(self) -> None:
        self.tabs.setCurrentWidget(self.settlement_tab)
        self.settlement_tab._on_copy_settlement_bill()

    def _open_shortcut_settings(self) -> None:
        self.tabs.setCurrentWidget(self.settings_tab)
        self.settings_tab.open_shortcut_subtab()

    def _on_try_wechat_sample(self, sample_text: str) -> None:
        self.tabs.setCurrentWidget(self.smart_entry_tab)
        self.smart_entry_tab.txt_chat_input.setPlainText(sample_text)
        self.smart_entry_tab.run_parse()

    def open_update_dialog(self) -> None:
        """打开版本管理与在线更新弹窗"""
        dlg = UpdateDialog(self.controller, parent=self)
        dlg.exec_()

    def _run_silent_startup_update_check(self) -> None:
        """后台静默检查更新，仅当发现未跳过的新版本时弹出升级提示"""
        self._startup_update_worker = UpdateCheckWorker(self.controller, self)
        self._startup_update_worker.finished_check.connect(self._on_silent_update_checked)
        self._startup_update_worker.start()

    def _on_silent_update_checked(self, result) -> None:
        if result and result.success and result.manifest and result.manifest.hot_keywords:
            self.controller.apply_hot_keywords_from_manifest(result.manifest)
            self.refresh_all()
        if (
            result
            and result.success
            and result.has_update
            and result.manifest
            and result.manifest.version != self.controller.app_config.skipped_version
        ):
            dlg = UpdateDialog(self.controller, initial_result=result, parent=self)
            dlg.exec_()

    def _apply_theme(self) -> None:
        mode = self.controller.app_config.theme_mode
        qss = ThemeManager.get_stylesheet(mode)
        self.setStyleSheet(qss)
        if mode == "dark":
            self.btn_theme.setText("亮色模式")
            self.btn_theme.setIcon(CartoonIconManager.get_icon("act_theme_light"))
        else:
            self.btn_theme.setText("暗色模式")
            self.btn_theme.setIcon(CartoonIconManager.get_icon("act_theme_dark"))

    def _on_toggle_theme(self) -> None:
        cfg = self.controller.app_config
        cfg.theme_mode = "dark" if cfg.theme_mode != "dark" else "light"
        self.controller.save_app_config(cfg)
        self._apply_theme()
        self.refresh_all()

    def _setup_clipboard_listener(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self) -> None:
        if not self.controller.app_config.auto_copy_parse:
            return
        text = QApplication.clipboard().text().strip()
        if not text or text == self._last_clipboard_text:
            return
        # 避免自身复制散码或结账单时触发循环识别
        if "上报数据明细：" in text or "分人算账汇总单" in text or "上报汇总（" in text:
            return
        self._last_clipboard_text = text
        if self.controller.app_config.auto_switch_to_wechat_on_copy:
            self.tabs.setCurrentWidget(self.smart_entry_tab)
        self.smart_entry_tab.txt_chat_input.setPlainText(text)
        self.smart_entry_tab.run_parse()

    def _setup_auto_backup_timer(self) -> None:
        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._on_auto_backup_tick)
        secs = max(10, self.controller.app_config.auto_save_seconds)
        self._backup_timer.start(secs * 1000)

    def _on_auto_backup_tick(self) -> None:
        db_path = self.controller.db_manager.db_path
        if db_path and str(db_path) != ":memory:":
            backup_file = db_path.parent / "lottery_auto_backup.db"
            try:
                self.controller.db_manager.backup_to(backup_file)
            except Exception:
                pass

    def refresh_all(self) -> None:
        """统一刷新顶部导航下拉框、五大标签页与状态栏"""
        self._updating_header = True
        try:
            # 1. 刷新盘口下拉框
            regions = self.controller.region_repo.list_regions()
            self.cmb_region.clear()
            for r in regions:
                self.cmb_region.addItem(r.name)
            r_idx = self.cmb_region.findText(self.controller.current_region)
            if r_idx >= 0:
                self.cmb_region.setCurrentIndex(r_idx)

            # 2. 刷新当前盘口客户下拉框
            clients = self.controller.client_repo.list_clients(self.controller.current_region)
            active_cli = self.controller.get_active_client(self.controller.current_region)
            self.cmb_active_client.clear()
            for c in clients:
                label = f"{c.name} (¥{c.total_bet:g})" if c.total_bet > 0 else c.name
                self.cmb_active_client.addItem(label, c.name)
            for i in range(self.cmb_active_client.count()):
                if self.cmb_active_client.itemData(i) == active_cli.name:
                    self.cmb_active_client.setCurrentIndex(i)
                    break

            # 3. 更新本命年徽章与萌宠头像
            zod = self.controller.app_config.base_zodiac
            self.lbl_zodiac_icon.setPixmap(CartoonIconManager.render_pixmap(f"zodiac_{zod}", 28))
            self.lbl_zodiac_badge.setText(f"本命年：{zod}年")
            self.setWindowTitle(
                f"特码智能收单与吃码风控系统 Pro v2.0 — [农历{zod}年 · 当前盘口: {self.controller.current_region}]"
            )
        finally:
            self._updating_header = False

        # 4. 刷新各子标签页
        self.dashboard_tab.refresh_data()
        self.smart_entry_tab.refresh_data()
        self.eat_report_tab.refresh_data()
        self.settlement_tab.refresh_data()
        self.history_review_tab.refresh_data()
        self.settings_tab.refresh_data()
        self.help_guide_tab.refresh_data()

        # 5. 更新底部状态栏
        region = self.controller.current_region
        active_c = self.controller.get_active_client(region)
        orders = self.controller.order_repo.list_orders(region)
        totals = self.controller.client_repo.get_region_total_bets_by_number(region)
        pool_sum = round(sum(totals.values()), 2)
        last_summary = self.controller.last_added_summary or "暂无新录订单"
        help_sc = self.controller.app_config.get_shortcut("switch_tab_6")

        self.lbl_status_info.setText(
            f"● 当前盘口: 【{region}】  |  ● 当前收单客户: 【{active_c.name} (赔率:{active_c.odds:g} 回水:{active_c.rebate*100:.1f}%)】  |  "
            f"● 订单笔数: {len(orders)} 笔  |  ● 全盘总金额: ¥ {pool_sum:g}  |  ● 最近入库: {last_summary[:45]}  |  ⌨️ 按 {help_sc} 查看使用说明"
        )

    def _on_settings_updated(self) -> None:
        secs = max(10, self.controller.app_config.auto_save_seconds)
        self._backup_timer.start(secs * 1000)
        self._rebuild_global_shortcuts()
        self._apply_theme()
        self.refresh_all()

    def _on_region_changed(self, region_name: str) -> None:
        if self._updating_header or not region_name:
            return
        self.controller.current_region = region_name
        self.refresh_all()

    def _on_active_client_changed(self, _index_or_text: str) -> None:
        if self._updating_header:
            return
        c_name = self.cmb_active_client.currentData()
        if c_name:
            self.controller.set_active_client(str(c_name), self.controller.current_region)
            self.refresh_all()

    def _on_add_region(self) -> None:
        name, ok = QInputDialog.getText(self, "新增盘口", "请输入新盘口名称（如：台湾、新加坡）：")
        if not ok or not name.strip():
            return
        rname = name.strip()
        existing = self.controller.region_repo.get_region(rname)
        if existing:
            QMessageBox.information(self, "提示", f"盘口「{rname}」已存在！")
            return
        regs = self.controller.region_repo.list_regions()
        self.controller.region_repo.save_region(
            RegionConfig(name=rname, display_order=len(regs) + 1)
        )
        self.controller.current_region = rname
        self.refresh_all()

    def _on_quick_add_client(self) -> None:
        region = self.controller.current_region
        name, ok = QInputDialog.getText(self, "快速新增收单客户", f"在【{region}】盘口下新增客户名称：")
        if not ok or not name.strip():
            return
        clean = name.strip()
        if clean[0].isdigit():
            QMessageBox.warning(self, "提示", "客户名称不能以纯数字开头！")
            return
        reg_cfg = self.controller.get_current_region_config()
        all_c = self.controller.client_repo.list_clients(region)
        if not any(c.name == clean for c in all_c):
            new_c = ClientProfile(
                id=None,
                region=region,
                name=clean,
                odds=reg_cfg.global_odds,
                rebate=reg_cfg.global_rebate,
                sort_order=len(all_c) + 1,
            )
            self.controller.client_repo.save_client(new_c)
        self.controller.set_active_client(clean, region)
        self.refresh_all()

    def _on_rename_current_client(self) -> None:
        """弹出对话框修改/修正当前激活客户名称，并级联更新其历史所有订单与盘口配置"""
        region = self.controller.current_region
        current_client = self.controller.get_active_client(region)
        old_name = current_client.name

        new_name, ok = QInputDialog.getText(
            self,
            "修正当前客户名",
            f"当前盘口：【{region}】\n请输入【{old_name}】的新名称：",
            text=old_name,
        )
        if not ok or not new_name.strip():
            return

        clean = new_name.strip()
        if clean == old_name:
            return

        if clean[0].isdigit():
            QMessageBox.warning(self, "名称不合规", "客户名称不能以数字开头，请输入合规名称！")
            return

        success = self.controller.client_repo.rename_client(region, old_name, clean)
        if success:
            self.controller.set_active_client(clean, region)
            self.refresh_all()
            QMessageBox.information(
                self,
                "客户名已修正",
                f"成功将客户【{old_name}】修正为【{clean}】！\n该客户的所有历史订单与押注统计已自动同步归属到新名称。",
            )
        else:
            QMessageBox.warning(
                self,
                "修正失败",
                f"盘口【{region}】中已存在名为【{clean}】的客户，或名称格式非法！",
            )

    def _on_import_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要导入的原版 Excel 表格 (.xlsm / .xlsx)",
            str(Path.cwd()),
            "Excel Files (*.xlsm *.xlsx)",
        )
        if not path:
            return
        try:
            stats = self.controller.migration_service.import_from_excel_workbook(path)
            self.controller.reload_runtime_configs()
            self.refresh_all()
            QMessageBox.information(
                self,
                "Excel 导入完成",
                f"成功从 Excel 导入数据：\n"
                f"• 识别词库：{stats.get('keywords', 0)} 条\n"
                f"• 客户档案：{stats.get('clients', 0)} 位\n"
                f"• 历史订单：{stats.get('orders', 0)} 笔",
            )
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", f"导入 Excel 时发生错误：\n{exc}")

    def _on_export_excel(self) -> None:
        default_name = f"特码风控与结算报表_{self.controller.current_region}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出完整 Excel 报表 (.xlsx)",
            str(Path.cwd() / default_name),
            "Excel Workbook (*.xlsx)",
        )
        if not path:
            return
        try:
            out_path = self.controller.migration_service.export_to_excel(
                path, region=self.controller.current_region
            )
            QMessageBox.information(
                self,
                "Excel 导出成功",
                f"已成功导出包含全盘汇总、风险排行、分人算账与订单明细的 Excel 报表：\n{out_path}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"导出 Excel 报表时发生错误：\n{exc}")
