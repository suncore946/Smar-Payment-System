"""
Tab 5: 客户管理、自定义配置与词库中心 (SettingsTab)
提供全方位的用户自定义配置选项：
1. 本命年生肖动态切换 (鼠~猪 12 生肖自动推算 1-49 号归属) 与识别参数配置
2. 客户档案、专属赔率与回水管理
3. 1,955+ 微信智能识别关键字词库增删查改
4. 自定义文字替换规则 & 自定义号码属性标签覆盖
5. 本地 SQLite 数据库一键备份与恢复
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict
from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from src.database.repositories import KeywordRepository
from src.domain.attribute_engine import NumberAttributeEngine
from src.domain.models import (
    AppConfig,
    BetMode,
    ClientProfile,
    CopyFormat,
     DEFAULT_SHORTCUTS,
    DefaultBetStyle,
    ReplaceRule,
    SHORTCUT_DEFINITIONS,
    SuiMode,
)
from src.services.app_controller import ApplicationController
from src.services.update_service import AutoUpdateService
from src.ui.icon_manager import CartoonIconManager
from src.ui.update_dialog import UpdateDialog
from src.version import APP_BUILD_DATE, APP_VERSION, OFFICIAL_GITHUB_REPO


class SettingsTab(QWidget):
    """系统配置、客户管理与词库中心标签页"""

    config_changed = pyqtSignal()

    def __init__(self, controller: ApplicationController, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._shortcut_editors: Dict[str, QKeySequenceEdit] = {}
        self._init_ui()
        self.refresh_data()

    def open_shortcut_subtab(self) -> None:
        """切换到「快捷键自定义设置」子标签页"""
        self.sub_tabs.setCurrentIndex(1)

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(
            self._build_general_config_page(),
            CartoonIconManager.get_icon("tab_settings"),
            "全局识别与系统设置",
        )
        self.sub_tabs.addTab(
            self._build_shortcut_config_page(),
            CartoonIconManager.get_icon("act_keyboard"),
            "快捷键自定义设置",
        )
        self.sub_tabs.addTab(
            self._build_client_mgmt_page(),
            CartoonIconManager.get_icon("kpi_client"),
            "客户档案与独立赔率/回水",
        )
        self.sub_tabs.addTab(
            self._build_keyword_mgmt_page(),
            CartoonIconManager.get_icon("act_parse"),
            "智能识别词库 (1955+ 词条)",
        )
        self.sub_tabs.addTab(
            self._build_replace_and_attr_page(),
            CartoonIconManager.get_icon("act_withdraw"),
            "自定义替换规则与号码属性",
        )
        self.sub_tabs.addTab(
            self._build_db_backup_page(),
            CartoonIconManager.get_icon("act_db_backup"),
            "本地数据库备份与维护",
        )
        self.sub_tabs.addTab(
            self._build_version_update_page(),
            CartoonIconManager.get_icon("act_update"),
            "版本管理与自动更新",
        )

        root_layout.addWidget(self.sub_tabs, 1)

    # =========================================================================
    # 子页 1: 全局识别与参数配置
    # =========================================================================
    def _build_general_config_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        form_card = QFrame()
        form_card.setProperty("card", True)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(12)

        lbl_title = QLabel("⚙️ 核心业务规则与智能识别参数设置")
        lbl_title.setProperty("sectionTitle", True)
        form_layout.addWidget(lbl_title)

        form = QFormLayout()
        form.setSpacing(12)

        self.cmb_base_zodiac = QComboBox()
        self.cmb_base_zodiac.addItems(list(NumberAttributeEngine.ZODIAC_ORDER))
        self.cmb_base_zodiac.currentTextChanged.connect(self._update_zodiac_preview)
        form.addRow("当前农历本命年生肖 (动态推算1-49号生肖):", self.cmb_base_zodiac)

        self.cmb_bet_mode = QComboBox()
        self.cmb_bet_mode.addItems([e.value for e in BetMode])
        form.addRow("平码/特码识别模式:", self.cmb_bet_mode)

        self.cmb_sui_mode = QComboBox()
        self.cmb_sui_mode.addItems([e.value for e in SuiMode])
        form.addRow("岁数转号码对照规则:", self.cmb_sui_mode)

        self.cmb_default_style = QComboBox()
        self.cmb_default_style.addItems([e.value for e in DefaultBetStyle])
        form.addRow("选号下单默认计费方式:", self.cmb_default_style)

        self.chk_decimal = QCheckBox("开启小数点识别（如 23.166元 识别为 23号 166元）")
        form.addRow("小数点智能识别:", self.chk_decimal)

        self.chk_auto_copy = QCheckBox("开启剪贴板监听（微信复制内容后自动填入识别框）")
        form.addRow("自动监听剪贴板:", self.chk_auto_copy)

        self.chk_auto_switch_wechat = QCheckBox("剪贴板自动识别时，自动跳转至「微信智能收单」页面")
        form.addRow("复制后自动跳转收单页:", self.chk_auto_switch_wechat)

        self.chk_error_popup = QCheckBox("遇到无法识别的语句时高亮弹窗提示")
        form.addRow("异常语句提醒:", self.chk_error_popup)

        self.chk_confirm_clear = QCheckBox("清空全盘或撤单操作前弹出二次确认保护")
        form.addRow("危险操作二次确认:", self.chk_confirm_clear)

        self.cmb_theme_mode = QComboBox()
        self.cmb_theme_mode.addItem("☀️ 亮色现代主题 (Light)", "light")
        self.cmb_theme_mode.addItem("🌙 暗夜护眼主题 (Dark)", "dark")
        form.addRow("系统界面外观主题:", self.cmb_theme_mode)

        self.cmb_copy_fmt = QComboBox()
        self.cmb_copy_fmt.addItems([e.value for e in CopyFormat])
        form.addRow("吃码上报复制散码默认格式:", self.cmb_copy_fmt)

        self.spin_auto_save = QSpinBox()
        self.spin_auto_save.setRange(5, 3600)
        self.spin_auto_save.setSingleStep(10)
        self.spin_auto_save.setSuffix(" 秒")
        form.addRow("自动备份检查间隔:", self.spin_auto_save)

        form_layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_save_cfg = QPushButton("💾 保存全局配置并立即生效")
        btn_save_cfg.setProperty("primary", True)
        btn_save_cfg.setMinimumHeight(38)
        btn_save_cfg.clicked.connect(self._on_save_general_config)
        btn_row.addWidget(btn_save_cfg, 2)

        btn_reset_cfg = QPushButton("🔄 恢复默认系统设置")
        btn_reset_cfg.setMinimumHeight(38)
        btn_reset_cfg.clicked.connect(self._on_reset_general_config)
        btn_row.addWidget(btn_reset_cfg, 1)

        form_layout.addLayout(btn_row)
        form_layout.addStretch()

        layout.addWidget(form_card, 1)

        # 右侧：12 生肖实时对照表预览
        preview_card = QFrame()
        preview_card.setProperty("card", True)
        prev_layout = QVBoxLayout(preview_card)
        prev_layout.setContentsMargins(16, 16, 16, 16)
        prev_layout.setSpacing(8)

        lbl_prev = QLabel("🐎 12 生肖与 1-49 号码实时映射预览 (随本命年自动变化)")
        lbl_prev.setProperty("sectionTitle", True)
        prev_layout.addWidget(lbl_prev)

        self.zodiac_preview_table = QTableWidget(12, 2)
        self.zodiac_preview_table.setHorizontalHeaderLabels(["生肖", "对应号码列表"])
        self.zodiac_preview_table.verticalHeader().setVisible(False)
        self.zodiac_preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.zodiac_preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.zodiac_preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        prev_layout.addWidget(self.zodiac_preview_table, 1)

        layout.addWidget(preview_card, 1)
        return page

    # =========================================================================
    # 子页 1.5: 快捷键自定义设置
    # =========================================================================
    def _build_shortcut_config_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        lbl_title = QLabel("⌨️ 全局与工作台快捷键自定义中心（点击按键框可直接按下新组合键录制）")
        lbl_title.setProperty("sectionTitle", True)
        top_bar.addWidget(lbl_title)
        top_bar.addStretch()

        btn_save_sc = QPushButton("💾 保存快捷键配置并立即生效")
        btn_save_sc.setProperty("primary", True)
        btn_save_sc.setMinimumHeight(36)
        btn_save_sc.clicked.connect(self._on_save_shortcuts)
        top_bar.addWidget(btn_save_sc)

        btn_reset_sc = QPushButton("🔄 一键恢复系统默认快捷键")
        btn_reset_sc.setProperty("warning", True)
        btn_reset_sc.setMinimumHeight(36)
        btn_reset_sc.clicked.connect(self._on_reset_default_shortcuts)
        top_bar.addWidget(btn_reset_sc)

        layout.addLayout(top_bar)

        self.shortcut_cfg_table = QTableWidget(len(SHORTCUT_DEFINITIONS), 6)
        self.shortcut_cfg_table.setHorizontalHeaderLabels(
            ["分类", "功能名称", "自定义按键录制 (点击后直接按键)", "系统默认键位", "单行重置", "功能详细说明"]
        )
        self.shortcut_cfg_table.verticalHeader().setVisible(False)
        self.shortcut_cfg_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.shortcut_cfg_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.shortcut_cfg_table.setAlternatingRowColors(True)
        self.shortcut_cfg_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.shortcut_cfg_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.shortcut_cfg_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.shortcut_cfg_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.shortcut_cfg_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.shortcut_cfg_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

        self._shortcut_editors.clear()
        for r_idx, defn in enumerate(SHORTCUT_DEFINITIONS):
            self.shortcut_cfg_table.setRowHeight(r_idx, 38)
            i0 = QTableWidgetItem(defn.category)
            i0.setTextAlignment(Qt.AlignCenter)
            i1 = QTableWidgetItem(defn.title)
            i3 = QTableWidgetItem(defn.default_key)
            i3.setTextAlignment(Qt.AlignCenter)
            i5 = QTableWidgetItem(defn.description)

            editor = QKeySequenceEdit()
            editor.setMinimumWidth(150)
            editor.setToolTip("点击此处后直接按下键盘组合键（如 Ctrl+R、F6、Alt+Q）")
            self._shortcut_editors[defn.action_id] = editor

            btn_row_reset = QPushButton("恢复默认")
            btn_row_reset.clicked.connect(
                lambda _checked=False, aid=defn.action_id, dkey=defn.default_key: self._reset_single_shortcut(aid, dkey)
            )

            self.shortcut_cfg_table.setItem(r_idx, 0, i0)
            self.shortcut_cfg_table.setItem(r_idx, 1, i1)
            self.shortcut_cfg_table.setCellWidget(r_idx, 2, editor)
            self.shortcut_cfg_table.setItem(r_idx, 3, i3)
            self.shortcut_cfg_table.setCellWidget(r_idx, 4, btn_row_reset)
            self.shortcut_cfg_table.setItem(r_idx, 5, i5)

        layout.addWidget(self.shortcut_cfg_table, 1)
        return page

    # =========================================================================
    # 子页 2: 客户档案与独立赔率/回水
    # =========================================================================
    def _build_client_mgmt_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        bar = QHBoxLayout()
        lbl = QLabel("👥 当前盘口客户列表与独立赔率/回水配置")
        lbl.setProperty("sectionTitle", True)
        bar.addWidget(lbl)
        bar.addStretch()

        btn_add_client = QPushButton("➕ 新增客户")
        btn_add_client.setProperty("primary", True)
        btn_add_client.clicked.connect(self._on_add_client)
        bar.addWidget(btn_add_client)

        btn_rename_client = QPushButton("✏️ 重命名选中客户")
        btn_rename_client.clicked.connect(self._on_rename_selected_client)
        bar.addWidget(btn_rename_client)

        btn_edit_rate = QPushButton("💰 修改选中客户赔率/回水")
        btn_edit_rate.setProperty("success", True)
        btn_edit_rate.clicked.connect(self._on_edit_selected_client_rate)
        bar.addWidget(btn_edit_rate)

        layout.addLayout(bar)

        self.client_mgmt_table = QTableWidget(0, 5)
        self.client_mgmt_table.setHorizontalHeaderLabels(
            ["排序号", "客户名称", "特码赔率", "回水比例 (%)", "当前累计收单 (元)"]
        )
        self.client_mgmt_table.verticalHeader().setVisible(False)
        self.client_mgmt_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.client_mgmt_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.client_mgmt_table.setAlternatingRowColors(True)
        self.client_mgmt_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.client_mgmt_table.cellDoubleClicked.connect(lambda _r, _c: self._on_edit_selected_client_rate())
        layout.addWidget(self.client_mgmt_table, 1)

        return page

    # =========================================================================
    # 子页 3: 智能识别词库 (1955+ 词条)
    # =========================================================================
    def _build_keyword_mgmt_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(QLabel("词库分类:"))
        self.cmb_kw_cat = QComboBox()
        self.cmb_kw_cat.addItems(list(KeywordRepository.CATEGORIES))
        self.cmb_kw_cat.currentIndexChanged.connect(self._refresh_keywords_list)
        top.addWidget(self.cmb_kw_cat)

        self.edit_kw_search = QLineEdit()
        self.edit_kw_search.setPlaceholderText("搜索关键字（如：各、肖、码）...")
        self.edit_kw_search.textChanged.connect(self._refresh_keywords_list)
        top.addWidget(self.edit_kw_search, 1)

        self.lbl_kw_count = QLabel("共 0 条")
        top.addWidget(self.lbl_kw_count)

        self.edit_new_kw = QLineEdit()
        self.edit_new_kw.setPlaceholderText("输入新识别关键字...")
        self.edit_new_kw.setMaximumWidth(200)
        top.addWidget(self.edit_new_kw)

        btn_add_kw = QPushButton("➕ 添加关键字")
        btn_add_kw.setProperty("primary", True)
        btn_add_kw.clicked.connect(self._on_add_keyword)
        top.addWidget(btn_add_kw)

        btn_del_kw = QPushButton("🗑️ 删除选中关键字")
        btn_del_kw.setProperty("danger", True)
        btn_del_kw.clicked.connect(self._on_delete_keyword)
        top.addWidget(btn_del_kw)

        layout.addLayout(top)

        self.list_keywords = QListWidget()
        self.list_keywords.setAlternatingRowColors(True)
        layout.addWidget(self.list_keywords, 1)
        return page

    # =========================================================================
    # 子页 4: 自定义替换规则与号码属性
    # =========================================================================
    def _build_replace_and_attr_page(self) -> QWidget:
        page = QWidget()
        splitter = QSplitter(Qt.Horizontal)
        layout = QHBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(splitter)

        # 左：自定义文字替换规则
        rep_card = QFrame()
        rep_card.setProperty("card", True)
        rep_layout = QVBoxLayout(rep_card)
        lbl_r = QLabel("🔄 微信识别前自定义文字替换规则 (对应原 文字替换.frm)")
        lbl_r.setProperty("sectionTitle", True)
        rep_layout.addWidget(lbl_r)

        rep_bar = QHBoxLayout()
        self.edit_find_str = QLineEdit()
        self.edit_find_str.setPlaceholderText("原文字 (如: 一米)")
        self.edit_rep_str = QLineEdit()
        self.edit_rep_str.setPlaceholderText("替换为 (如: 各1)")
        btn_add_rule = QPushButton("➕ 保存替换规则")
        btn_add_rule.setProperty("primary", True)
        btn_add_rule.clicked.connect(self._on_add_replace_rule)
        btn_del_rule = QPushButton("删除选中")
        btn_del_rule.setProperty("danger", True)
        btn_del_rule.clicked.connect(self._on_delete_replace_rule)
        rep_bar.addWidget(self.edit_find_str)
        rep_bar.addWidget(self.edit_rep_str)
        rep_bar.addWidget(btn_add_rule)
        rep_bar.addWidget(btn_del_rule)
        rep_layout.addLayout(rep_bar)

        self.table_rules = QTableWidget(0, 3)
        self.table_rules.setHorizontalHeaderLabels(["查找文本", "替换为", "状态"])
        self.table_rules.verticalHeader().setVisible(False)
        self.table_rules.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_rules.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_rules.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rep_layout.addWidget(self.table_rules, 1)
        splitter.addWidget(rep_card)

        # 右：自定义属性标签对应的号码集合
        attr_card = QFrame()
        attr_card.setProperty("card", True)
        attr_layout = QVBoxLayout(attr_card)
        lbl_a = QLabel("🏷️ 自定义属性标签 / 号码组合 (可在微信识别中直接使用)")
        lbl_a.setProperty("sectionTitle", True)
        attr_layout.addWidget(lbl_a)

        attr_bar = QHBoxLayout()
        self.edit_tag_name = QLineEdit()
        self.edit_tag_name.setPlaceholderText("属性名 (如: 特选大码)")
        self.edit_tag_nums = QLineEdit()
        self.edit_tag_nums.setPlaceholderText("号码列表 (如: 06,08,18,28,38,48)")
        btn_save_tag = QPushButton("💾 保存属性")
        btn_save_tag.setProperty("primary", True)
        btn_save_tag.clicked.connect(self._on_save_custom_tag)
        btn_del_tag = QPushButton("还原/删除")
        btn_del_tag.setProperty("warning", True)
        btn_del_tag.clicked.connect(self._on_delete_custom_tag)
        attr_bar.addWidget(self.edit_tag_name, 1)
        attr_bar.addWidget(self.edit_tag_nums, 2)
        attr_bar.addWidget(btn_save_tag)
        attr_bar.addWidget(btn_del_tag)
        attr_layout.addLayout(attr_bar)

        self.table_custom_tags = QTableWidget(0, 2)
        self.table_custom_tags.setHorizontalHeaderLabels(["自定义属性名称", "包含号码列表"])
        self.table_custom_tags.verticalHeader().setVisible(False)
        self.table_custom_tags.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_custom_tags.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_custom_tags.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_custom_tags.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        attr_layout.addWidget(self.table_custom_tags, 1)
        splitter.addWidget(attr_card)

        return page

    # =========================================================================
    # 子页 5: 本地数据库备份与维护
    # =========================================================================
    def _build_db_backup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("card", True)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(14)

        lbl = QLabel("🗄️ 本地 SQLite 数据库管理、备份与 Excel 双向迁移")
        lbl.setProperty("sectionTitle", True)
        c_layout.addWidget(lbl)

        self.lbl_db_info = QLabel("")
        self.lbl_db_info.setStyleSheet("font-size: 13px; line-height: 1.6;")
        c_layout.addWidget(self.lbl_db_info)

        btn_grid = QGridLayout()
        btn_grid.setSpacing(12)

        btn_backup = QPushButton("💾 一键备份本地 SQLite 数据库 (.db)")
        btn_backup.setProperty("primary", True)
        btn_backup.setMinimumHeight(42)
        btn_backup.clicked.connect(self._on_backup_db)
        btn_grid.addWidget(btn_backup, 0, 0)

        btn_restore = QPushButton("📂 从备份文件恢复 SQLite 数据库 (.db)")
        btn_restore.setMinimumHeight(42)
        btn_restore.clicked.connect(self._on_restore_db)
        btn_grid.addWidget(btn_restore, 0, 1)

        btn_reseed = QPushButton("🔄 重新导入内置 1,955+ 默认关键字词库")
        btn_reseed.setProperty("success", True)
        btn_reseed.setMinimumHeight(42)
        btn_reseed.clicked.connect(self._on_reseed_keywords)
        btn_grid.addWidget(btn_reseed, 1, 0)

        btn_vacuum = QPushButton("🧹 压缩优化数据库空间 (VACUUM)")
        btn_vacuum.setMinimumHeight(42)
        btn_vacuum.clicked.connect(self._on_vacuum_db)
        btn_grid.addWidget(btn_vacuum, 1, 1)

        btn_open_dir = QPushButton("📁 打开系统用户数据目录 (AppData)")
        btn_open_dir.setMinimumHeight(42)
        btn_open_dir.clicked.connect(self._on_open_data_folder)
        btn_grid.addWidget(btn_open_dir, 2, 0, 1, 2)

        c_layout.addLayout(btn_grid)
        c_layout.addStretch()
        layout.addWidget(card)
        return page

    # =========================================================================
    # 子页 6: 版本管理与自动更新配置
    # =========================================================================
    def _build_version_update_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # 左侧：更新源与策略配置卡片
        left_card = QFrame()
        left_card.setProperty("card", True)
        l_layout = QVBoxLayout(left_card)
        l_layout.setContentsMargins(18, 16, 18, 16)
        l_layout.setSpacing(12)

        lbl_head = QLabel(f"🚀 版本管理与在线更新设置 (当前版本: v{APP_VERSION} · 构建于 {APP_BUILD_DATE})")
        lbl_head.setProperty("sectionTitle", True)
        l_layout.addWidget(lbl_head)

        form = QFormLayout()
        form.setSpacing(12)

        self.cmb_update_mode = QComboBox()
        self.cmb_update_mode.addItem("🐙 GitHub 官方 Releases 自动更新 (已锁定防篡改)", "github_api")
        self.cmb_update_mode.setEnabled(False)
        form.addRow("更新源托管方式:", self.cmb_update_mode)

        self.edit_update_url = QLineEdit()
        self.edit_update_url.setText(OFFICIAL_GITHUB_REPO)
        self.edit_update_url.setReadOnly(True)
        self.edit_update_url.setStyleSheet(
            "background-color: #f1f3f4; color: #3c4043; font-family: Consolas, monospace; font-weight: bold;"
        )
        form.addRow("官方更新仓库:", self.edit_update_url)

        lbl_lock_notice = QLabel("🔒 提示：本系统在线更新源已强制写死锁定为官方仓库，严防篡改。")
        lbl_lock_notice.setStyleSheet("color: #d93025; font-size: 12px; font-weight: bold;")
        form.addRow("", lbl_lock_notice)

        self.edit_mirror_prefix = QLineEdit()
        self.edit_mirror_prefix.setPlaceholderText("可选，如 https://ghfast.top/ (用于国内加速下载 GitHub Release)")
        form.addRow("GitHub 下载加速镜像前缀:", self.edit_mirror_prefix)

        self.chk_auto_check_startup = QCheckBox("每次启动软件后在后台静默检查是否有新版本")
        form.addRow("启动自动检查更新:", self.chk_auto_check_startup)

        l_layout.addLayout(form)

        btn_row1 = QHBoxLayout()
        btn_save_upd = QPushButton("💾 保存更新策略 (镜像/启动检查)")
        btn_save_upd.setProperty("primary", True)
        btn_save_upd.setMinimumHeight(38)
        btn_save_upd.clicked.connect(self._on_save_update_config)
        btn_row1.addWidget(btn_save_upd)

        btn_check_now = QPushButton("🔍 立即检查更新 & 查看更新日志")
        btn_check_now.setIcon(CartoonIconManager.get_icon("act_update"))
        btn_check_now.setProperty("success", True)
        btn_check_now.setMinimumHeight(38)
        btn_check_now.clicked.connect(self._on_open_update_dialog)
        btn_row1.addWidget(btn_check_now)
        l_layout.addLayout(btn_row1)

        btn_export_manifest = QPushButton("📦 一键生成当前版本发布清单 (version.json，供发布到 GitHub Release)")
        btn_export_manifest.setMinimumHeight(36)
        btn_export_manifest.clicked.connect(self._on_export_version_manifest)
        l_layout.addWidget(btn_export_manifest)

        l_layout.addStretch()
        layout.addWidget(left_card, 1)

        # 右侧：Git 仓库与发布更新操作说明
        right_card = QFrame()
        right_card.setProperty("card", True)
        r_layout = QVBoxLayout(right_card)
        r_layout.setContentsMargins(18, 16, 18, 16)
        r_layout.setSpacing(8)

        lbl_guide = QLabel("📖 官方更新源工作原理与发布流程指南")
        lbl_guide.setProperty("sectionTitle", True)
        r_layout.addWidget(lbl_guide)

        lbl_deploy_html = QLabel(
            f"<b>🔒 官方在线更新源已锁定</b><br>"
            f"当前系统已绑定官方 GitHub 仓库：<code>{OFFICIAL_GITHUB_REPO}</code>。<br>"
            f"所有客户端将统一从此仓库的 <b>Releases</b> 与最新标签获取升级包，有效避免恶意劫持。<br><br>"
            f"<b>🚀 如何发布新版本更新？</b><br>"
            f"1. <b>生成新版本清单</b>：点击左侧「一键生成当前版本发布清单」，自动生成包含最新可执行文件 SHA256 签名的 <code>version.json</code>；<br>"
            f"2. <b>推送至 GitHub Releases</b>：在 GitHub 仓库 <code>{OFFICIAL_GITHUB_REPO}</code> 中新建 Release（如 <code>v2.2.0</code>），将打包好的 <code>特码智能收单风控系统Pro.exe</code> 和 <code>version.json</code> 上传为附件；<br>"
            f"3. <b>CI/CD 全自动发布</b>：只要向仓库推送 <code>v*</code> 标签（如 <code>git tag v2.2.0 && git push origin v2.2.0</code>），内置的 GitHub Actions 就会全自动编译并发布！<br><br>"
            f"<b>⚡ 国内用户加速下载</b><br>"
            f"如果用户在中国大陆网络环境下下载 GitHub Release 较慢，可在左侧填入加速镜像前缀（如 <code>https://ghfast.top/</code>），系统会自动拼接前缀实现高速直连下载。<br><br>"
            f"<b>💡 词库热更新</b><br>"
            f"在发布 <code>version.json</code> 时，若在 <code>hot_keywords</code> 中添加新的微信识别语法词，客户端检查更新时会自动合并入本地词库，无需重启软件。"
        )
        lbl_deploy_html.setWordWrap(True)
        lbl_deploy_html.setStyleSheet("font-size: 13px; line-height: 1.6;")
        r_layout.addWidget(lbl_deploy_html)
        r_layout.addStretch()

        layout.addWidget(right_card, 1)
        return page

    # =========================================================================
    # 数据刷新与事件响应
    # =========================================================================
    def refresh_data(self) -> None:
        cfg = self.controller.app_config

        self.cmb_base_zodiac.blockSignals(True)
        self.cmb_base_zodiac.setCurrentText(cfg.base_zodiac)
        self.cmb_base_zodiac.blockSignals(False)
        self._update_zodiac_preview(cfg.base_zodiac)

        self.cmb_bet_mode.setCurrentText(cfg.bet_mode.value)
        self.cmb_sui_mode.setCurrentText(cfg.sui_mode.value)
        self.cmb_default_style.setCurrentText(cfg.default_bet_style.value)
        self.chk_decimal.setChecked(cfg.recognize_decimal)
        self.chk_auto_copy.setChecked(cfg.auto_copy_parse)
        self.chk_auto_switch_wechat.setChecked(cfg.auto_switch_to_wechat_on_copy)
        self.chk_error_popup.setChecked(cfg.error_popup)
        self.chk_confirm_clear.setChecked(cfg.confirm_before_clear)
        t_idx = self.cmb_theme_mode.findData(cfg.theme_mode)
        if t_idx >= 0:
            self.cmb_theme_mode.setCurrentIndex(t_idx)
        self.cmb_copy_fmt.setCurrentText(cfg.report_copy_format.value)
        self.spin_auto_save.setValue(cfg.auto_save_seconds)

        u_idx = self.cmb_update_mode.findData("github_api")
        if u_idx >= 0:
            self.cmb_update_mode.blockSignals(True)
            self.cmb_update_mode.setCurrentIndex(u_idx)
            self.cmb_update_mode.blockSignals(False)
        self.edit_update_url.setText(OFFICIAL_GITHUB_REPO)
        self.edit_mirror_prefix.setText(cfg.update_mirror_prefix)
        self.chk_auto_check_startup.setChecked(cfg.auto_check_update_on_startup)

        self._refresh_shortcuts_editors()
        self._refresh_clients_table()
        self._refresh_keywords_list()
        self._refresh_replace_rules()
        self._refresh_custom_tags()
        self._refresh_db_info()

    def _refresh_shortcuts_editors(self) -> None:
        cfg = self.controller.app_config
        for defn in SHORTCUT_DEFINITIONS:
            editor = self._shortcut_editors.get(defn.action_id)
            if editor is not None:
                key_str = cfg.get_shortcut(defn.action_id)
                editor.setKeySequence(QKeySequence(key_str))

    def _reset_single_shortcut(self, action_id: str, default_key: str) -> None:
        editor = self._shortcut_editors.get(action_id)
        if editor is not None:
            editor.setKeySequence(QKeySequence(default_key))

    def _on_save_shortcuts(self) -> None:
        new_shortcuts: Dict[str, str] = {}
        seen_keys: Dict[str, str] = {}
        for defn in SHORTCUT_DEFINITIONS:
            editor = self._shortcut_editors.get(defn.action_id)
            key_str = editor.keySequence().toString() if editor else defn.default_key
            # 若输入了多个按键序列（如逗号分隔），仅取第一组组合键
            if ", " in key_str:
                key_str = key_str.split(", ")[0].strip()
            if key_str:
                norm = key_str.upper()
                if norm in seen_keys:
                    QMessageBox.warning(
                        self,
                        "快捷键冲突提醒",
                        f"快捷键「{key_str}」同时被分配给了：\n"
                        f"• {seen_keys[norm]}\n"
                        f"• {defn.title}\n\n"
                        f"请为其中一个功能更换其他按键组合！",
                    )
                    return
                seen_keys[norm] = defn.title
            new_shortcuts[defn.action_id] = key_str

        cfg = self.controller.app_config
        cfg.shortcuts = new_shortcuts
        self.controller.save_app_config(cfg)
        self._refresh_shortcuts_editors()
        self.config_changed.emit()
        QMessageBox.information(self, "快捷键已生效", "自定义快捷键配置已保存到本地数据库并全局生效！")

    def _on_reset_default_shortcuts(self) -> None:
        cfg = self.controller.app_config
        cfg.reset_shortcuts()
        self.controller.save_app_config(cfg)
        self._refresh_shortcuts_editors()
        self.config_changed.emit()
        QMessageBox.information(self, "已恢复默认", "全部 20 项全局与工作台快捷键已恢复为系统默认键位！")

    def _update_zodiac_preview(self, zodiac_name: str) -> None:
        if not zodiac_name:
            return
        temp_engine = NumberAttributeEngine(base_zodiac=zodiac_name)
        z_map = temp_engine.get_zodiac_numbers_map()
        self.zodiac_preview_table.setRowCount(12)
        for idx, z in enumerate(NumberAttributeEngine.ZODIAC_ORDER):
            nums_str = ", ".join(f"{n:02d}" for n in z_map.get(z, []))
            i0 = QTableWidgetItem(f"{z} ({'本命年' if z == zodiac_name else '平肖'})")
            i0.setIcon(CartoonIconManager.get_icon(f"zodiac_{z}"))
            i0.setTextAlignment(Qt.AlignCenter)
            i1 = QTableWidgetItem(nums_str)
            self.zodiac_preview_table.setItem(idx, 0, i0)
            self.zodiac_preview_table.setItem(idx, 1, i1)

    def _on_save_general_config(self) -> None:
        cfg = self.controller.app_config
        cfg.base_zodiac = self.cmb_base_zodiac.currentText()
        cfg.bet_mode = BetMode(self.cmb_bet_mode.currentText())
        cfg.sui_mode = SuiMode(self.cmb_sui_mode.currentText())
        cfg.default_bet_style = DefaultBetStyle(self.cmb_default_style.currentText())
        cfg.recognize_decimal = self.chk_decimal.isChecked()
        cfg.auto_copy_parse = self.chk_auto_copy.isChecked()
        cfg.auto_switch_to_wechat_on_copy = self.chk_auto_switch_wechat.isChecked()
        cfg.error_popup = self.chk_error_popup.isChecked()
        cfg.confirm_before_clear = self.chk_confirm_clear.isChecked()
        cfg.theme_mode = self.cmb_theme_mode.currentData() or "light"
        cfg.report_copy_format = CopyFormat(self.cmb_copy_fmt.currentText())
        cfg.auto_save_seconds = self.spin_auto_save.value()

        self.controller.save_app_config(cfg)
        self.config_changed.emit()
        QMessageBox.information(self, "保存成功", "全局识别与系统参数配置已写入本地数据库并立即生效！")

    def _on_reset_general_config(self) -> None:
        default_cfg = AppConfig(shortcuts=dict(self.controller.app_config.shortcuts))
        self.controller.save_app_config(default_cfg)
        self.refresh_data()
        self.config_changed.emit()
        QMessageBox.information(self, "恢复完成", "已将全局识别与系统参数恢复为出厂默认配置！")

    def _refresh_clients_table(self) -> None:
        clients = self.controller.client_repo.list_clients(self.controller.current_region)
        self.client_mgmt_table.setRowCount(len(clients))
        for r_idx, c in enumerate(clients):
            vals = [
                str(c.sort_order),
                c.name,
                f"{c.odds:g}",
                f"{c.rebate * 100:.2f}%",
                f"{c.total_bet:g}",
            ]
            for c_idx, text in enumerate(vals):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                self.client_mgmt_table.setItem(r_idx, c_idx, item)

    def _on_add_client(self) -> None:
        region = self.controller.current_region
        name, ok = QInputDialog.getText(self, "新增客户", "请输入新客户名称（不能以纯数字开头）：")
        if not ok or not name.strip():
            return
        clean = name.strip()
        if clean[0].isdigit():
            QMessageBox.warning(self, "格式错误", "客户名称不能以数字开头！")
            return
        existing = self.controller.client_repo.get_client(region, clean)
        if existing:
            QMessageBox.warning(self, "已存在", f"客户「{clean}」已存在！")
            return
        reg_cfg = self.controller.get_current_region_config()
        all_c = self.controller.client_repo.list_clients(region)
        new_c = ClientProfile(
            id=None,
            region=region,
            name=clean,
            odds=reg_cfg.global_odds,
            rebate=reg_cfg.global_rebate,
            sort_order=len(all_c) + 1,
        )
        self.controller.client_repo.save_client(new_c)
        self._refresh_clients_table()
        self.config_changed.emit()

    def _on_rename_selected_client(self) -> None:
        row = self.client_mgmt_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要重命名的客户行！")
            return
        old_name = self.client_mgmt_table.item(row, 1).text()
        new_name, ok = QInputDialog.getText(
            self, "重命名客户", f"将客户「{old_name}」重命名为：", text=old_name
        )
        if ok and new_name.strip():
            if self.controller.client_repo.rename_client(
                self.controller.current_region, old_name, new_name.strip()
            ):
                self._refresh_clients_table()
                self.config_changed.emit()
            else:
                QMessageBox.warning(self, "失败", "新名称不能以数字开头，且不能与已有客户重名！")

    def _on_edit_selected_client_rate(self) -> None:
        row = self.client_mgmt_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要修改赔率/回水的客户行！")
            return
        c_name = self.client_mgmt_table.item(row, 1).text()
        client = self.controller.client_repo.get_client(self.controller.current_region, c_name)
        if not client:
            return
        odds, ok1 = QInputDialog.getDouble(
            self, f"修改 {c_name} 赔率", "请输入特码赔率：", client.odds, 1.0, 200.0, 2
        )
        if not ok1:
            return
        reb_pct, ok2 = QInputDialog.getDouble(
            self, f"修改 {c_name} 回水比例(%)", "请输入回水百分比 (%)：", client.rebate * 100.0, 0.0, 100.0, 2
        )
        if not ok2:
            return
        client.odds = odds
        client.rebate = round(reb_pct / 100.0, 4)
        self.controller.client_repo.save_client(client)
        self._refresh_clients_table()
        self.config_changed.emit()

    def _refresh_keywords_list(self) -> None:
        cat = self.cmb_kw_cat.currentText()
        search = self.edit_kw_search.text().strip()
        kws = self.controller.keyword_repo.get_keywords(cat)
        if search:
            kws = [k for k in kws if search in k]
        self.list_keywords.clear()
        self.list_keywords.addItems(kws)
        self.lbl_kw_count.setText(f"共 {len(kws)} 条")

    def _on_add_keyword(self) -> None:
        kw = self.edit_new_kw.text().strip()
        if not kw:
            return
        cat = self.cmb_kw_cat.currentText()
        self.controller.keyword_repo.add_keyword(cat, kw)
        self.controller.reload_runtime_configs()
        self.edit_new_kw.clear()
        self._refresh_keywords_list()
        self.config_changed.emit()

    def _on_delete_keyword(self) -> None:
        item = self.list_keywords.currentItem()
        if not item:
            return
        kw = item.text()
        cat = self.cmb_kw_cat.currentText()
        self.controller.keyword_repo.delete_keyword(cat, kw)
        self.controller.reload_runtime_configs()
        self._refresh_keywords_list()
        self.config_changed.emit()

    def _refresh_replace_rules(self) -> None:
        self._rules = self.controller.replace_repo.list_rules(only_enabled=False)
        self.table_rules.setRowCount(len(self._rules))
        for r_idx, r in enumerate(self._rules):
            i0 = QTableWidgetItem(r.find_text)
            i0.setData(Qt.UserRole, r.id)
            i1 = QTableWidgetItem(r.replace_text)
            i2 = QTableWidgetItem("已启用" if r.is_enabled else "已停用")
            for col, it in enumerate((i0, i1, i2)):
                it.setTextAlignment(Qt.AlignCenter)
                self.table_rules.setItem(r_idx, col, it)

    def _on_add_replace_rule(self) -> None:
        f_txt = self.edit_find_str.text().strip()
        r_txt = self.edit_rep_str.text().strip()
        if not f_txt:
            QMessageBox.warning(self, "提示", "请输入要查找替换的原文字！")
            return
        self.controller.replace_repo.save_rule(
            ReplaceRule(id=None, find_text=f_txt, replace_text=r_txt, is_enabled=True)
        )
        self.controller.reload_runtime_configs()
        self.edit_find_str.clear()
        self.edit_rep_str.clear()
        self._refresh_replace_rules()
        self.config_changed.emit()

    def _on_delete_replace_rule(self) -> None:
        row = self.table_rules.currentRow()
        if row < 0 or row >= len(self._rules):
            return
        rule_id = self._rules[row].id
        if rule_id is not None:
            self.controller.replace_repo.delete_rule(rule_id)
            self.controller.reload_runtime_configs()
            self._refresh_replace_rules()
            self.config_changed.emit()

    def _refresh_custom_tags(self) -> None:
        overrides = self.controller.config_repo.load_attribute_overrides()
        items = sorted(overrides.items())
        self.table_custom_tags.setRowCount(len(items))
        for r_idx, (tag, nums) in enumerate(items):
            i0 = QTableWidgetItem(tag)
            i0.setTextAlignment(Qt.AlignCenter)
            nums_text = nums if isinstance(nums, str) else ", ".join(f"{n:02d}" for n in nums)
            i1 = QTableWidgetItem(nums_text)
            self.table_custom_tags.setItem(r_idx, 0, i0)
            self.table_custom_tags.setItem(r_idx, 1, i1)

    def _on_save_custom_tag(self) -> None:
        tag = self.edit_tag_name.text().strip()
        nums_str = self.edit_tag_nums.text().strip()
        if not tag or not nums_str:
            QMessageBox.warning(self, "提示", "请输入自定义属性名称及对应的号码列表！")
            return
        nums = []
        for p in nums_str.replace("，", ",").replace(" ", ",").split(","):
            if p.strip().isdigit():
                n = int(p.strip())
                if 1 <= n <= 49:
                    nums.append(n)
        if not nums:
            QMessageBox.warning(self, "提示", "未解析到 1~49 之间的有效号码！")
            return
        overrides = self.controller.config_repo.load_attribute_overrides()
        overrides[tag] = sorted(set(nums))
        self.controller.config_repo.save_attribute_overrides(overrides)
        self.controller.reload_runtime_configs()
        self.edit_tag_name.clear()
        self.edit_tag_nums.clear()
        self._refresh_custom_tags()
        self.config_changed.emit()

    def _on_delete_custom_tag(self) -> None:
        row = self.table_custom_tags.currentRow()
        if row < 0:
            return
        tag = self.table_custom_tags.item(row, 0).text()
        overrides = self.controller.config_repo.load_attribute_overrides()
        if tag in overrides:
            del overrides[tag]
            self.controller.config_repo.save_attribute_overrides(overrides)
            self.controller.reload_runtime_configs()
            self._refresh_custom_tags()
            self.config_changed.emit()

    def _refresh_db_info(self) -> None:
        db_path = self.controller.db_manager.db_path
        size_kb = db_path.stat().st_size / 1024.0 if db_path and db_path.exists() else 0.0
        kw_cnt = len(self.controller.keyword_repo.get_keywords("全部关键字"))
        self.lbl_db_info.setText(
            f"📍 <b>本地数据库路径：</b> {db_path}<br>"
            f"📦 <b>数据库文件大小：</b> {size_kb:.1f} KB<br>"
            f"🔑 <b>内置识别关键字总数：</b> {kw_cnt} 条"
        )

    def _on_backup_db(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "备份 SQLite 数据库", "lottery_backup.db", "SQLite Database (*.db)"
        )
        if path:
            self.controller.db_manager.backup_to(path)
            QMessageBox.information(self, "备份成功", f"数据库已成功备份至：\n{path}")

    def _on_restore_db(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择要恢复的 SQLite 备份文件", "", "SQLite Database (*.db)"
        )
        if path and Path(path).exists():
            reply = QMessageBox.warning(
                self,
                "确认恢复数据库",
                "恢复备份将覆盖当前数据库中的所有数据，确定继续吗？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.controller.db_manager.restore_from(path)
                self.controller.reload_runtime_configs()
                self.refresh_data()
                self.config_changed.emit()
                QMessageBox.information(self, "恢复完成", "数据库已从备份成功恢复！")

    def _on_reseed_keywords(self) -> None:
        self.controller.migration_service.load_from_default_seed_json()
        self.controller.reload_runtime_configs()
        self.refresh_data()
        self.config_changed.emit()
        QMessageBox.information(self, "词库恢复完成", "已重新导入内置 1,955+ 默认关键字词库！")

    def _on_vacuum_db(self) -> None:
        with self.controller.db_manager.connection() as conn:
            conn.execute("VACUUM")
        self._refresh_db_info()
        QMessageBox.information(self, "优化完成", "SQLite 数据库空间压缩与索引优化已完成！")

    def _on_open_data_folder(self) -> None:
        db_path = self.controller.db_manager.db_path
        if db_path and str(db_path) != ":memory:":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(db_path.parent.resolve())))

    def _on_update_mode_changed(self) -> None:
        mode = self.cmb_update_mode.currentData()
        if mode == "github_api":
            self.edit_update_url.setPlaceholderText("输入 GitHub 仓库名，例如: myuser/lottery-risk-pro")
        elif mode == "gitee_api":
            self.edit_update_url.setPlaceholderText("输入 Gitee 码云仓库名，例如: myuser/lottery-risk-pro")
        else:
            self.edit_update_url.setPlaceholderText("输入 version.json 完整 URL，例如: https://your-domain.com/version.json")

    def _on_save_update_config(self) -> None:
        cfg = self.controller.app_config
        # 强制锁定官方更新源
        cfg.update_source_mode = "github_api"
        cfg.update_repo_or_url = OFFICIAL_GITHUB_REPO
        cfg.update_mirror_prefix = self.edit_mirror_prefix.text().strip()
        cfg.auto_check_update_on_startup = self.chk_auto_check_startup.isChecked()
        self.controller.save_app_config(cfg)
        self.config_changed.emit()
        QMessageBox.information(
            self,
            "保存成功",
            f"在线更新策略已成功保存！\n\n官方更新源已永久锁定：{OFFICIAL_GITHUB_REPO}\n镜像加速与启动检查更新配置已生效。",
        )

    def _on_open_update_dialog(self) -> None:
        dlg = UpdateDialog(self.controller, parent=self)
        dlg.exec_()

    def _on_export_version_manifest(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出当前版本发布清单 (version.json)",
            "version.json",
            "JSON Manifest (*.json)",
        )
        if not path:
            return
        import sys
        exe_candidate = Path(sys.executable) if getattr(sys, "frozen", False) else (Path.cwd() / "特码智能收单风控系统Pro.exe")
        manifest = AutoUpdateService.generate_version_manifest_file(
            exe_path=exe_candidate,
            output_json_path=path,
        )
        QMessageBox.information(
            self,
            "发布清单导出成功",
            f"已成功生成包含当前版本号 (v{manifest.version}) 与 SHA256 签名的发布清单：\n{path}\n\n"
            f"您可以将该文件与 .exe 一起上传至 GitHub/Gitee Releases 或您的自定义服务器！",
        )
