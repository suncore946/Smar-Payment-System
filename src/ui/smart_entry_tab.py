"""
微信/QQ智能收单与极速录单工作台 (SmartEntryTab)
包含：
1. 微信/QQ多行聊天记录粘贴、拖拽、剪贴板自动识别、插入各/共、一键负数、可编辑预览表格与入库
2. 单号/多号键盘极速盲打录入（支持每注/平摊，回车即录）
3. 可视化选号助手（12生肖、波色、单双大小、五行、头尾、阵营多条件交并集选号与反码）
"""

from __future__ import annotations
from typing import Callable, List, Optional
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QShortcut,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from src.domain.models import BetMode, DefaultBetStyle, ParsedBetItem, SuiMode
from src.services.app_controller import ApplicationController
from src.services.wechat_parser_service import WeChatParserService
from .icon_manager import CartoonIconManager
from .styles import ThemeManager


class SmartEntryTab(QWidget):
    """微信/QQ智能收单与选号极速录入视图组件"""

    SAMPLE_WECHAT_TEXT = (
        "牛虎兔各码25\n"
        "羊各码80\n"
        "羊狗各五\n"
        "01.12.24.11.07.03各50\n"
        "3头4头每个数10\n"
        "大共500元"
    )

    def __init__(
        self,
        controller: ApplicationController,
        on_order_submitted: Callable[[], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.on_order_submitted = on_order_submitted
        self._parsed_items: List[ParsedBetItem] = []
        self._picker_buttons: List[QPushButton] = []
        self._picker_inverted: bool = False
        self._updating_table = False
        self._init_ui()
        self._setup_shortcuts()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        main_splitter = QSplitter(Qt.Horizontal)

        # ==================================================================
        # 左侧：微信/QQ聊天记录智能识别工作台
        # ==================================================================
        left_group = QGroupBox("💬 微信 / QQ 聊天记录智能提取工作台")
        left_layout = QVBoxLayout(left_group)
        left_layout.setSpacing(8)

        # 识别模式快捷栏
        mode_bar = QHBoxLayout()
        mode_bar.addWidget(QLabel("识别模式:"))
        self.cmb_bet_mode = QComboBox()
        for m in BetMode:
            self.cmb_bet_mode.addItem(m.value, m)
        self.cmb_bet_mode.currentIndexChanged.connect(self._on_mode_options_changed)
        mode_bar.addWidget(self.cmb_bet_mode)

        mode_bar.addWidget(QLabel("岁数模式:"))
        self.cmb_sui_mode = QComboBox()
        self.cmb_sui_mode.addItem("岁按各号 (岁模式_各)", SuiMode.SUI_EACH)
        self.cmb_sui_mode.addItem("岁按生肖 (岁模式_生肖)", SuiMode.SUI_ZODIAC)
        self.cmb_sui_mode.currentIndexChanged.connect(self._on_mode_options_changed)
        mode_bar.addWidget(self.cmb_sui_mode)

        self.chk_decimal = QCheckBox("识别小数点")
        self.chk_decimal.setChecked(self.controller.app_config.recognize_decimal)
        self.chk_decimal.toggled.connect(self._on_mode_options_changed)
        mode_bar.addWidget(self.chk_decimal)

        self.chk_auto_clipboard = QCheckBox("自动监听剪贴板识别")
        self.chk_auto_clipboard.setChecked(self.controller.app_config.auto_copy_parse)
        self.chk_auto_clipboard.toggled.connect(self._on_mode_options_changed)
        mode_bar.addWidget(self.chk_auto_clipboard)
        mode_bar.addStretch()
        left_layout.addLayout(mode_bar)

        # 粘贴聊天记录输入框
        self.txt_chat_input = QPlainTextEdit()
        self.txt_chat_input.setPlaceholderText(
            "在此粘贴或拖拽微信/QQ报单聊天记录（支持多条混合识别）...\n"
            "例如：\n"
            "  牛虎兔各码25\n"
            "  羊狗各五\n"
            "  1到25各30\n"
            "  014头各50\n"
            "  23.166元  40.165元"
        )
        self.txt_chat_input.setMaximumHeight(135)
        left_layout.addWidget(self.txt_chat_input)

        # 操作按钮栏
        action_bar = QHBoxLayout()
        action_bar.setSpacing(6)

        self.btn_paste_and_parse = QPushButton("粘贴并识别")
        self.btn_paste_and_parse.setIcon(CartoonIconManager.get_icon("act_paste"))
        self.btn_paste_and_parse.clicked.connect(self.paste_and_parse)
        action_bar.addWidget(self.btn_paste_and_parse)

        self.btn_parse_now = QPushButton("立即识别 (Ctrl+Enter)")
        self.btn_parse_now.setIcon(CartoonIconManager.get_icon("act_parse"))
        self.btn_parse_now.clicked.connect(self.run_parse)
        action_bar.addWidget(self.btn_parse_now)

        self.btn_insert_ge = QPushButton("插入“各”字")
        self.btn_insert_ge.setIcon(CartoonIconManager.get_icon("act_plus"))
        self.btn_insert_ge.setObjectName("SecondaryBtn")
        self.btn_insert_ge.clicked.connect(lambda: self._insert_keyword_at_cursor("各"))
        action_bar.addWidget(self.btn_insert_ge)

        self.btn_insert_gong = QPushButton("插入“共”字")
        self.btn_insert_gong.setIcon(CartoonIconManager.get_icon("act_plus"))
        self.btn_insert_gong.setObjectName("SecondaryBtn")
        self.btn_insert_gong.clicked.connect(lambda: self._insert_keyword_at_cursor("共"))
        action_bar.addWidget(self.btn_insert_gong)

        self.btn_negate = QPushButton("一键负数 (撤单冲抵)")
        self.btn_negate.setIcon(CartoonIconManager.get_icon("act_negate"))
        self.btn_negate.setObjectName("WarningBtn")
        self.btn_negate.clicked.connect(self._on_negate_clicked)
        action_bar.addWidget(self.btn_negate)

        self.btn_sample = QPushButton("填入示例")
        self.btn_sample.setObjectName("SecondaryBtn")
        self.btn_sample.clicked.connect(self._on_fill_sample_clicked)
        action_bar.addWidget(self.btn_sample)

        self.btn_clear_input = QPushButton("清空")
        self.btn_clear_input.setIcon(CartoonIconManager.get_icon("act_clear"))
        self.btn_clear_input.setObjectName("SecondaryBtn")
        self.btn_clear_input.clicked.connect(self._on_clear_clicked)
        action_bar.addWidget(self.btn_clear_input)

        left_layout.addLayout(action_bar)

        # 识别结果预览表格
        self.tbl_parsed_preview = QTableWidget(0, 7)
        self.tbl_parsed_preview.setHorizontalHeaderLabels(
            ["状态", "识别号码 (可双击改)", "单号金额 (可双击改)", "号数", "小计金额", "原始片段", "操作"]
        )
        self.tbl_parsed_preview.verticalHeader().setVisible(False)
        self.tbl_parsed_preview.setAlternatingRowColors(True)
        self.tbl_parsed_preview.setSelectionBehavior(QAbstractItemView.SelectRows)
        hdr = self.tbl_parsed_preview.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Stretch)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.tbl_parsed_preview.itemChanged.connect(self._on_preview_item_edited)
        left_layout.addWidget(self.tbl_parsed_preview, 1)

        # 底部确认添加栏
        submit_bar = QHBoxLayout()
        self.lbl_parsed_summary = QLabel("识别条数: 0 条 | 本单合计: ¥ 0")
        self.lbl_parsed_summary.setStyleSheet("font-size: 15px; font-weight: bold; color: #1D4ED8;")
        submit_bar.addWidget(self.lbl_parsed_summary)
        submit_bar.addStretch()

        self.btn_confirm_add = QPushButton("确认添加到当前客户账单 (F2)")
        self.btn_confirm_add.setIcon(CartoonIconManager.get_icon("act_add_order"))
        self.btn_confirm_add.setObjectName("SuccessBtn")
        self.btn_confirm_add.setMinimumHeight(38)
        self.btn_confirm_add.setMinimumWidth(220)
        self.btn_confirm_add.clicked.connect(self.confirm_add_to_ledger)
        submit_bar.addWidget(self.btn_confirm_add)
        left_layout.addLayout(submit_bar)

        self.lbl_last_added = QLabel("最近一次添加: （暂无）")
        self.lbl_last_added.setStyleSheet("color: #64748B; font-size: 12px;")
        left_layout.addWidget(self.lbl_last_added)

        main_splitter.addWidget(left_group)

        # ==================================================================
        # 右侧：极速盲打录入 + 可视化选号助手
        # ==================================================================
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # 1. 极速盲打输入区（单号/多号快速输入）
        quick_group = QGroupBox("⚡ 单号 / 多号键盘极速盲打录入（输入后按回车即录）")
        q_layout = QGridLayout(quick_group)
        q_layout.setSpacing(8)

        q_layout.addWidget(QLabel("号码/属性串:"), 0, 0)
        self.edt_quick_code = QLineEdit()
        self.edt_quick_code.setPlaceholderText("如: 041628 或 兔蛇08（两位一组自动切分）")
        self.edt_quick_code.textChanged.connect(self._update_quick_preview)
        self.edt_quick_code.returnPressed.connect(lambda: self.edt_quick_amount.setFocus())
        q_layout.addWidget(self.edt_quick_code, 0, 1, 1, 2)

        q_layout.addWidget(QLabel("下注金额:"), 0, 3)
        self.edt_quick_amount = QLineEdit()
        self.edt_quick_amount.setPlaceholderText("输入金额回车即入库")
        self.edt_quick_amount.textChanged.connect(self._update_quick_preview)
        self.edt_quick_amount.returnPressed.connect(self._on_quick_submit)
        q_layout.addWidget(self.edt_quick_amount, 0, 4)

        self.rad_quick_each = QRadioButton("每注 (各号)")
        self.rad_quick_flat = QRadioButton("平摊 (共)")
        self.rad_quick_each.setChecked(True)
        self.rad_quick_each.toggled.connect(self._update_quick_preview)
        q_layout.addWidget(self.rad_quick_each, 1, 0)
        q_layout.addWidget(self.rad_quick_flat, 1, 1)

        self.lbl_quick_preview = QLabel("预览: 0 个号 | 单号: ¥0 | 总计: ¥0")
        self.lbl_quick_preview.setStyleSheet("color: #059669; font-weight: bold;")
        q_layout.addWidget(self.lbl_quick_preview, 1, 2, 1, 2)

        self.btn_quick_add = QPushButton("➕ 极速入库")
        self.btn_quick_add.setObjectName("SuccessBtn")
        self.btn_quick_add.clicked.connect(self._on_quick_submit)
        q_layout.addWidget(self.btn_quick_add, 1, 4)

        right_layout.addWidget(quick_group)

        # 2. 可视化选号助手
        picker_group = QGroupBox("🎯 可视化选号助手（支持多条件交集 / 并集 / 反码组合选号）")
        p_layout = QVBoxLayout(picker_group)
        p_layout.setSpacing(6)

        # 选号条件组合模式与反码栏
        p_top_bar = QHBoxLayout()
        p_top_bar.addWidget(QLabel("多选逻辑:"))
        self.cmb_picker_logic = QComboBox()
        self.cmb_picker_logic.addItem("智能交并集 (有交集取交集，无交集取并集)", "auto")
        self.cmb_picker_logic.addItem("并集模式 (满足任一条件即可)", "union")
        self.cmb_picker_logic.addItem("严格交集 (必须同时满足所有选中条件)", "intersection")
        self.cmb_picker_logic.currentIndexChanged.connect(self._update_picker_preview)
        p_top_bar.addWidget(self.cmb_picker_logic, 1)

        self.btn_picker_invert = QPushButton("🔄 取反码")
        self.btn_picker_invert.setCheckable(True)
        self.btn_picker_invert.setObjectName("TagChipBtn")
        self.btn_picker_invert.toggled.connect(self._on_picker_invert_toggled)
        p_top_bar.addWidget(self.btn_picker_invert)

        self.btn_picker_reset = QPushButton("🧹 清除选中")
        self.btn_picker_reset.setObjectName("SecondaryBtn")
        self.btn_picker_reset.clicked.connect(self._reset_picker_selection)
        p_top_bar.addWidget(self.btn_picker_reset)
        p_layout.addLayout(p_top_bar)

        # 属性标签滚动面板
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        chips_layout = QVBoxLayout(scroll_content)
        chips_layout.setContentsMargins(4, 4, 4, 4)
        chips_layout.setSpacing(6)

        categories = [
            ("十二生肖", ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]),
            ("波色组合", ["红波", "蓝波", "绿波", "红单", "红双", "蓝单", "蓝双", "绿单", "绿双", "红大", "红小", "蓝大", "蓝小", "绿大", "绿小"]),
            ("单双大小", ["单", "双", "大", "小", "大单", "小单", "大双", "小双", "合单", "合双", "合大", "合小"]),
            ("五行属性", ["金", "木", "水", "火", "土", "家禽", "野兽", "天肖", "地肖", "吉肖", "凶肖", "阴肖", "阳肖", "男肖", "女肖"]),
            ("头数尾数", ["0头", "1头", "2头", "3头", "4头", "0尾", "1尾", "2尾", "3尾", "4尾", "5尾", "6尾", "7尾", "8尾", "9尾", "大尾", "小尾"]),
        ]

        for cat_title, tags in categories:
            row_box = QGridLayout()
            row_box.setSpacing(4)
            lbl_cat = QLabel(f"{cat_title}:")
            lbl_cat.setStyleSheet("font-weight: bold; color: #1E40AF; min-width: 62px;")
            row_box.addWidget(lbl_cat, 0, 0)
            for idx, tag in enumerate(tags):
                r = idx // 8
                c = (idx % 8) + 1
                btn = QPushButton(tag)
                btn.setCheckable(True)
                btn.setObjectName("TagChipBtn")
                btn.toggled.connect(self._update_picker_preview)
                row_box.addWidget(btn, r, c)
                self._picker_buttons.append(btn)
            chips_layout.addLayout(row_box)

        scroll.setWidget(scroll_content)
        p_layout.addWidget(scroll, 1)

        # 选号结果展示与下单栏
        self.lbl_picker_numbers = QLabel("已选号码 (0个): 暂无")
        self.lbl_picker_numbers.setWordWrap(True)
        self.lbl_picker_numbers.setStyleSheet(
            "background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px; font-weight: bold; color: #0F172A;"
        )
        p_layout.addWidget(self.lbl_picker_numbers)

        p_bottom = QHBoxLayout()
        self.rad_picker_each = QRadioButton("每个号金额")
        self.rad_picker_flat = QRadioButton("总金额平摊")
        p_group = QButtonGroup(self)
        p_group.addButton(self.rad_picker_each)
        p_group.addButton(self.rad_picker_flat)
        if self.controller.app_config.default_bet_style == DefaultBetStyle.ZODIAC_FLAT:
            self.rad_picker_flat.setChecked(True)
        else:
            self.rad_picker_each.setChecked(True)
        self.rad_picker_each.toggled.connect(self._update_picker_preview)

        p_bottom.addWidget(self.rad_picker_each)
        p_bottom.addWidget(self.rad_picker_flat)
        p_bottom.addWidget(QLabel("金额:"))
        self.spin_picker_amount = QDoubleSpinBox()
        self.spin_picker_amount.setRange(0.0, 1000000.0)
        self.spin_picker_amount.setDecimals(1)
        self.spin_picker_amount.setValue(20.0)
        self.spin_picker_amount.valueChanged.connect(self._update_picker_preview)
        p_bottom.addWidget(self.spin_picker_amount)

        self.lbl_picker_calc = QLabel("单号: ¥0 | 总计: ¥0")
        self.lbl_picker_calc.setStyleSheet("font-weight: bold; color: #1D4ED8;")
        p_bottom.addWidget(self.lbl_picker_calc)
        p_bottom.addStretch()

        self.btn_picker_submit = QPushButton("➕ 添加选号订单")
        self.btn_picker_submit.setObjectName("SuccessBtn")
        self.btn_picker_submit.clicked.connect(self._on_picker_submit)
        p_bottom.addWidget(self.btn_picker_submit)
        p_layout.addLayout(p_bottom)

        right_layout.addWidget(picker_group, 1)
        main_splitter.addWidget(right_container)
        main_splitter.setStretchFactor(0, 6)
        main_splitter.setStretchFactor(1, 5)

        root_layout.addWidget(main_splitter, 1)

    def _setup_shortcuts(self) -> None:
        # 快捷键统一由 MainWindow 的全局可配置快捷键管理器动态绑定与更新
        pass

    def focus_quick_code_input(self) -> None:
        """将焦点定位到单号/多号极速盲打输入框"""
        self.edt_quick_code.setFocus()
        self.edt_quick_code.selectAll()

    def _on_mode_options_changed(self) -> None:
        cfg = self.controller.app_config
        cfg.bet_mode = self.cmb_bet_mode.currentData()
        cfg.sui_mode = self.cmb_sui_mode.currentData()
        cfg.recognize_decimal = self.chk_decimal.isChecked()
        cfg.auto_copy_parse = self.chk_auto_clipboard.isChecked()
        self.controller.save_app_config(cfg)
        if self.txt_chat_input.toPlainText().strip():
            self.run_parse()

    def _insert_keyword_at_cursor(self, kw: str) -> None:
        cursor = self.txt_chat_input.textCursor()
        cursor.insertText(kw)
        self.txt_chat_input.setFocus()
        self.run_parse()

    def paste_and_parse(self) -> None:
        cb_text = QApplication.clipboard().text()
        if cb_text and cb_text.strip():
            self.txt_chat_input.setPlainText(cb_text.strip())
            self.run_parse()

    def _on_fill_sample_clicked(self) -> None:
        self.txt_chat_input.setPlainText(self.SAMPLE_WECHAT_TEXT)
        self.run_parse()

    def _on_clear_clicked(self) -> None:
        self.txt_chat_input.clear()
        self._parsed_items.clear()
        self._render_parsed_table()

    def run_parse(self) -> None:
        raw = self.txt_chat_input.toPlainText().strip()
        if not raw:
            self._parsed_items.clear()
            self._render_parsed_table()
            return
        self._parsed_items = self.controller.parser_service.parse_text(raw)
        self._render_parsed_table()
        invalid_cnt = sum(1 for it in self._parsed_items if not it.is_valid)
        if invalid_cnt > 0 and self.controller.app_config.error_popup:
            QMessageBox.warning(
                self,
                "识别异常提醒",
                f"共有 {invalid_cnt} 条内容未能正常识别，请在预览表中双击修正或插入“各/共”字后再试。",
            )

    def _on_negate_clicked(self) -> None:
        if not self._parsed_items:
            self.run_parse()
        WeChatParserService.negate_items(self._parsed_items)
        self._render_parsed_table()

    def _render_parsed_table(self) -> None:
        self._updating_table = True
        try:
            dark_mode = self.controller.app_config.theme_mode == "dark"
            self.tbl_parsed_preview.setRowCount(len(self._parsed_items))
            bold_font = QFont("Microsoft YaHei UI", 10, QFont.Bold)
            grand_total = 0.0

            for r_idx, item in enumerate(self._parsed_items):
                self.tbl_parsed_preview.setRowHeight(r_idx, 28)
                item.validate()
                if item.is_valid:
                    grand_total = round(grand_total + item.total_amount, 2)

                status_str = "○ 正常" if item.is_valid else f"错 ({item.error_message})"
                st_cell = QTableWidgetItem(status_str)
                st_cell.setFlags(st_cell.flags() & ~Qt.ItemIsEditable)
                st_cell.setTextAlignment(Qt.AlignCenter)
                st_cell.setFont(bold_font)
                st_cell.setForeground(
                    QBrush(ThemeManager.get_pnl_color(1 if item.is_valid else -1, dark_mode))
                )

                num_cell = QTableWidgetItem(item.formatted_numbers)
                num_cell.setTextAlignment(Qt.AlignCenter)

                amt_cell = QTableWidgetItem(f"{item.per_number_amount:g}")
                amt_cell.setTextAlignment(Qt.AlignCenter)
                amt_cell.setFont(bold_font)

                cnt_cell = QTableWidgetItem(str(item.count))
                cnt_cell.setFlags(cnt_cell.flags() & ~Qt.ItemIsEditable)
                cnt_cell.setTextAlignment(Qt.AlignCenter)

                tot_cell = QTableWidgetItem(f"{item.total_amount:g}")
                tot_cell.setFlags(tot_cell.flags() & ~Qt.ItemIsEditable)
                tot_cell.setTextAlignment(Qt.AlignCenter)
                tot_cell.setFont(bold_font)

                raw_cell = QTableWidgetItem(item.raw_fragment)
                raw_cell.setFlags(raw_cell.flags() & ~Qt.ItemIsEditable)

                btn_del = QPushButton("删除")
                btn_del.setObjectName("DangerBtn")
                btn_del.clicked.connect(lambda _, idx=r_idx: self._remove_parsed_row(idx))

                self.tbl_parsed_preview.setItem(r_idx, 0, st_cell)
                self.tbl_parsed_preview.setItem(r_idx, 1, num_cell)
                self.tbl_parsed_preview.setItem(r_idx, 2, amt_cell)
                self.tbl_parsed_preview.setItem(r_idx, 3, cnt_cell)
                self.tbl_parsed_preview.setItem(r_idx, 4, tot_cell)
                self.tbl_parsed_preview.setItem(r_idx, 5, raw_cell)
                self.tbl_parsed_preview.setCellWidget(r_idx, 6, btn_del)

            self.lbl_parsed_summary.setText(
                f"识别条数: {len(self._parsed_items)} 条 | 本单合计: ¥ {grand_total:,.2f}".rstrip("0").rstrip(".")
            )
        finally:
            self._updating_table = False

    def _on_preview_item_edited(self, cell: QTableWidgetItem) -> None:
        if self._updating_table:
            return
        row = cell.row()
        col = cell.column()
        if row < 0 or row >= len(self._parsed_items):
            return
        item = self._parsed_items[row]
        if col == 1:
            nums = [int(x) for x in cell.text().replace("，", ",").split(",") if x.strip().isdigit()]
            item.numbers = nums
            item.total_amount = round(item.per_number_amount * len(nums), 2)
        elif col == 2:
            try:
                val = float(cell.text())
                item.per_number_amount = round(val, 3)
                item.total_amount = round(val * len(item.numbers), 2)
            except ValueError:
                pass
        self._render_parsed_table()

    def _remove_parsed_row(self, idx: int) -> None:
        if 0 <= idx < len(self._parsed_items):
            self._parsed_items.pop(idx)
            self._render_parsed_table()

    def confirm_add_to_ledger(self) -> None:
        if not self._parsed_items:
            raw = self.txt_chat_input.toPlainText().strip()
            if raw:
                self.run_parse()
        if not self._parsed_items:
            QMessageBox.information(self, "提示", "当前没有可添加的识别内容！")
            return

        invalid = [it for it in self._parsed_items if not it.validate()]
        if invalid:
            QMessageBox.warning(self, "存在无效条目", "请先修正或删除标记为“错”的条目后再添加入库！")
            return

        raw_text = self.txt_chat_input.toPlainText().strip()
        order = self.controller.submit_bet_items(self._parsed_items, raw_text=raw_text)
        if order:
            self.lbl_last_added.setText(
                f"最近一次添加 ({order.client_name} | ¥{order.total_amount:g}): {self.controller.last_added_summary}"
            )
            self.txt_chat_input.clear()
            self._parsed_items.clear()
            self._render_parsed_table()
            self.on_order_submitted()

    # ==================================================================
    # 极速盲打录入与选号助手逻辑
    # ==================================================================
    def _update_quick_preview(self) -> None:
        code = self.edt_quick_code.text().strip()
        amt_str = self.edt_quick_amount.text().strip()
        try:
            amt = float(amt_str) if amt_str else 0.0
        except ValueError:
            amt = 0.0
        is_flat = self.rad_quick_flat.isChecked()
        item = self.controller.parser_service.parse_quick_input(code, amt if amt != 0 else 1.0, is_flat)
        if not item:
            self.lbl_quick_preview.setText("预览: 0 个号 | 单号: ¥0 | 总计: ¥0")
            return
        if amt == 0:
            self.lbl_quick_preview.setText(f"预览: {item.formatted_numbers} (共{item.count}号) | 请输入金额")
        else:
            self.lbl_quick_preview.setText(
                f"预览: {item.formatted_numbers} ({item.count}号) | 单号: ¥{item.per_number_amount:g} | 总计: ¥{item.total_amount:g}"
            )

    def _on_quick_submit(self) -> None:
        code = self.edt_quick_code.text().strip()
        amt_str = self.edt_quick_amount.text().strip()
        try:
            amt = float(amt_str)
        except ValueError:
            QMessageBox.warning(self, "金额错误", "请输入有效的数字金额！")
            return
        is_flat = self.rad_quick_flat.isChecked()
        item = self.controller.parser_service.parse_quick_input(code, amt, is_flat)
        if not item or not item.validate():
            QMessageBox.warning(self, "号码错误", "未识别到有效的 01-49 号码或生肖属性！")
            return

        order = self.controller.submit_bet_items([item], raw_text=item.raw_fragment)
        if order:
            self.lbl_last_added.setText(
                f"极速录入成功 ({order.client_name} | ¥{order.total_amount:g}): {order.parsed_content}"
            )
            self.edt_quick_code.clear()
            self.edt_quick_amount.clear()
            self.edt_quick_code.setFocus()
            self.on_order_submitted()

    def _on_picker_invert_toggled(self, checked: bool) -> None:
        self._picker_inverted = checked
        self._update_picker_preview()

    def _reset_picker_selection(self) -> None:
        for btn in self._picker_buttons:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        self.btn_picker_invert.setChecked(False)
        self._picker_inverted = False
        self._update_picker_preview()

    def _get_picker_numbers(self) -> tuple[List[str], List[int]]:
        selected_tags = [btn.text() for btn in self._picker_buttons if btn.isChecked()]
        logic_mode = self.cmb_picker_logic.currentData() or "auto"
        nums = self.controller.attr_engine.resolve_selection(selected_tags, mode=logic_mode)
        if self._picker_inverted and nums:
            nums = self.controller.attr_engine.invert_numbers(nums)
        return selected_tags, nums

    def _update_picker_preview(self) -> None:
        tags, nums = self._get_picker_numbers()
        amt = self.spin_picker_amount.value()
        if not nums:
            self.lbl_picker_numbers.setText("已选号码 (0个): 请点击上方属性标签进行组合选号")
            self.lbl_picker_calc.setText("单号: ¥0 | 总计: ¥0")
            return

        num_str = self.controller.attr_engine.format_nums(nums)
        inv_tag = " [反码]" if self._picker_inverted else ""
        self.lbl_picker_numbers.setText(
            f"已选条件 ({'+'.join(tags)}{inv_tag}) -> 共 {len(nums)} 个号:\n{num_str}"
        )
        if self.rad_picker_each.isChecked():
            per_amt = round(amt, 2)
            tot_amt = round(amt * len(nums), 2)
        else:
            per_amt = round(amt / len(nums), 2)
            tot_amt = round(amt, 2)
        self.lbl_picker_calc.setText(f"单号: ¥{per_amt:g} | 总计: ¥{tot_amt:g}")

    def _on_picker_submit(self) -> None:
        tags, nums = self._get_picker_numbers()
        amt = self.spin_picker_amount.value()
        if not nums or amt <= 0:
            QMessageBox.information(self, "提示", "请先选择至少一个属性条件并输入大于0的金额！")
            return

        if self.rad_picker_each.isChecked():
            per_amt = round(amt, 2)
            tot_amt = round(amt * len(nums), 2)
            mode_word = "各"
        else:
            per_amt = round(amt / len(nums), 2)
            tot_amt = round(amt, 2)
            mode_word = "共"

        inv_prefix = "反码" if self._picker_inverted else ""
        raw_desc = f"[选号助手]{inv_prefix}{','.join(tags)}{mode_word}{amt:g}"
        item = ParsedBetItem(
            numbers=nums,
            per_number_amount=per_amt,
            total_amount=tot_amt,
            raw_fragment=raw_desc,
        )
        order = self.controller.submit_bet_items([item], raw_text=raw_desc)
        if order:
            self.lbl_last_added.setText(
                f"选号助手添加成功 ({order.client_name} | ¥{order.total_amount:g}): {order.parsed_content}"
            )
            self._reset_picker_selection()
            self.on_order_submitted()

    def refresh_data(self) -> None:
        cfg = self.controller.app_config
        self.cmb_bet_mode.blockSignals(True)
        for i in range(self.cmb_bet_mode.count()):
            if self.cmb_bet_mode.itemData(i) == cfg.bet_mode:
                self.cmb_bet_mode.setCurrentIndex(i)
                break
        self.cmb_bet_mode.blockSignals(False)

        self.cmb_sui_mode.blockSignals(True)
        for i in range(self.cmb_sui_mode.count()):
            if self.cmb_sui_mode.itemData(i) == cfg.sui_mode:
                self.cmb_sui_mode.setCurrentIndex(i)
                break
        self.cmb_sui_mode.blockSignals(False)

        self.chk_decimal.blockSignals(True)
        self.chk_decimal.setChecked(cfg.recognize_decimal)
        self.chk_decimal.blockSignals(False)

        self.chk_auto_clipboard.blockSignals(True)
        self.chk_auto_clipboard.setChecked(cfg.auto_copy_parse)
        self.chk_auto_clipboard.blockSignals(False)

        # 动态同步按钮上的快捷键提示
        sc_parse = cfg.get_shortcut("parse_wechat")
        sc_submit = cfg.get_shortcut("submit_order")
        sc_paste = cfg.get_shortcut("paste_and_parse")
        sc_clear = cfg.get_shortcut("clear_wechat_input")
        sc_neg = cfg.get_shortcut("negate_parsed")
        self.btn_parse_now.setText(f"立即识别 ({sc_parse})" if sc_parse else "立即识别")
        self.btn_confirm_add.setText(f"确认添加到当前客户账单 ({sc_submit})" if sc_submit else "确认添加到当前客户账单")
        self.btn_paste_and_parse.setToolTip(f"粘贴剪贴板内容并立即识别 ({sc_paste})")
        self.btn_clear_input.setToolTip(f"清空输入框与预览列表 ({sc_clear})")
        self.btn_negate.setToolTip(f"将识别结果转为负数冲抵 ({sc_neg})")

        self._update_picker_preview()
