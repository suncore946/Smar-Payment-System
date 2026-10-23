"""
Tab 3: 吃码上报与飞单风控中心 (EatReportTab)
完整复刻并增强原 Excel `吃码上报.frm`、`吃码上报_保存或撤回上报.frm`、`按比例吃码或上报.frm`、
`按号吃码或上报.frm` 与 `吃码上报_保存和查看.frm` 的全部功能。
"""

from __future__ import annotations
from typing import List
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from src.domain.models import CopyFormat, RiskItem
from src.services.app_controller import ApplicationController
from src.ui.icon_manager import CartoonIconManager
from src.ui.styles import ThemeManager


class SnapshotViewerDialog(QDialog):
    """历史吃码上报风控快照查看弹窗"""

    def __init__(self, controller: ApplicationController, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("历史吃码与上报风控快照记录")
        self.resize(880, 560)
        self._init_ui()
        self._load_snapshots()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(280)
        self.list_widget.currentRowChanged.connect(self._on_select_snapshot)
        layout.addWidget(self.list_widget)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["号码", "生肖", "总汇总", "自己吃", "预备上报", "已经上报", "吃码风险值"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

    def _load_snapshots(self) -> None:
        self.snapshots = self.controller.eat_repo.list_snapshots(self.controller.current_region)
        self.list_widget.clear()
        for snap in self.snapshots:
            self.list_widget.addItem(f"[{snap['created_at']}] {snap['title']}")
        if self.snapshots:
            self.list_widget.setCurrentRow(0)

    def _on_select_snapshot(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.snapshots):
            return
        rows = self.snapshots[idx].get("data", [])
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            vals = [
                f"{int(row.get('number', 0)):02d}",
                str(row.get("zodiac", "")),
                f"{float(row.get('total_bet', 0)):g}",
                f"{float(row.get('eat_amount', 0)):g}",
                f"{float(row.get('report_amount', 0)):g}",
                f"{float(row.get('reported_amount', 0)):g}",
                f"{float(row.get('eat_risk_value', 0)):+.2f}",
            ]
            for c_idx, text in enumerate(vals):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r_idx, c_idx, item)


class EatReportTab(QWidget):
    """吃码上报与飞单风控中心标签页"""

    data_changed = pyqtSignal()

    def __init__(self, controller: ApplicationController, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._sort_mode: str = "total_desc"
        self._updating_slider = False
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        # ================= 左侧：1-49 号吃码与上报风控总表 =================
        left_card = QFrame()
        left_card.setProperty("card", True)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        header_row = QHBoxLayout()
        lbl_title = QLabel("🛡️ 1-49 号吃码 / 预备上报 / 风险值总表")
        lbl_title.setProperty("sectionTitle", True)
        header_row.addWidget(lbl_title)
        header_row.addStretch()

        header_row.addWidget(QLabel("排序方式:"))
        self.cmb_sort = QComboBox()
        self.cmb_sort.addItems([
            "按总汇总从高到低 (默认)",
            "按吃码后风险从高到低",
            "按预备上报从高到低",
            "按号码 01-49 顺序",
        ])
        self.cmb_sort.currentIndexChanged.connect(self._on_sort_changed)
        header_row.addWidget(self.cmb_sort)

        btn_edit_eat = QPushButton("✏️ 修改选中号吃码")
        btn_edit_eat.clicked.connect(self._on_edit_selected_eat)
        header_row.addWidget(btn_edit_eat)

        btn_clear_eat = QPushButton("🔄 撤销全部吃码(全转上报)")
        btn_clear_eat.setProperty("warning", True)
        btn_clear_eat.clicked.connect(self._on_clear_all_eat)
        header_row.addWidget(btn_clear_eat)

        left_layout.addLayout(header_row)

        # KPI 汇总条
        self.lbl_summary_bar = QLabel("收单总额: 0 | 自己吃码总额: 0 | 预备上报总额: 0 | 已上报总额: 0 | 吃码最大风险: 0")
        self.lbl_summary_bar.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding: 6px 10px; background: rgba(37,99,235,0.08); border-radius: 6px;"
        )
        left_layout.addWidget(self.lbl_summary_bar)

        self.risk_table = QTableWidget(49, 8)
        self.risk_table.setHorizontalHeaderLabels([
            "号码",
            "生肖",
            "总汇总",
            "自己吃(双击可改)",
            "预备上报",
            "已经上报",
            "满单风险值",
            "吃码后风险值",
        ])
        self.risk_table.verticalHeader().setVisible(False)
        self.risk_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.risk_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.risk_table.setAlternatingRowColors(True)
        self.risk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.risk_table.cellDoubleClicked.connect(self._on_table_double_clicked)
        left_layout.addWidget(self.risk_table, 1)

        splitter.addWidget(left_card)

        # ================= 右侧：风控策略计算器 + 复制散码 + 多上庄管理 =================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # --- 卡片 1: 智能吃码与反推计算器 ---
        calc_card = QFrame()
        calc_card.setProperty("card", True)
        calc_layout = QVBoxLayout(calc_card)
        calc_layout.setContentsMargins(12, 10, 12, 10)
        calc_layout.setSpacing(8)

        lbl_calc = QLabel("🧮 智能吃码计算器 (支持平均吃码 / 最大亏损二分反推 / 按比例 / 按属性)")
        lbl_calc.setProperty("sectionTitle", True)
        calc_layout.addWidget(lbl_calc)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Row 0: 打算平均吃码 + 滑块
        grid.addWidget(QLabel("打算每码平均吃:"), 0, 0)
        self.spin_avg_eat = QDoubleSpinBox()
        self.spin_avg_eat.setRange(0.0, 10000000.0)
        self.spin_avg_eat.setDecimals(0)
        self.spin_avg_eat.setSingleStep(50.0)
        grid.addWidget(self.spin_avg_eat, 0, 1)

        btn_apply_avg = QPushButton("应用平均吃码")
        btn_apply_avg.setProperty("primary", True)
        btn_apply_avg.clicked.connect(self._on_apply_avg_eat)
        grid.addWidget(btn_apply_avg, 0, 2)

        self.slider_eat = QSlider(Qt.Horizontal)
        self.slider_eat.setRange(0, 5000)
        self.slider_eat.valueChanged.connect(self._on_slider_changed)
        grid.addWidget(self.slider_eat, 0, 3)

        # Row 1: 打算最多亏损二分反推
        grid.addWidget(QLabel("打算最多亏损额:"), 1, 0)
        self.spin_max_loss = QDoubleSpinBox()
        self.spin_max_loss.setRange(0.0, 100000000.0)
        self.spin_max_loss.setDecimals(0)
        self.spin_max_loss.setSingleStep(500.0)
        self.spin_max_loss.setValue(2000.0)
        grid.addWidget(self.spin_max_loss, 1, 1)

        btn_apply_max_loss = QPushButton("⚡ 二分反推最佳吃码")
        btn_apply_max_loss.setProperty("success", True)
        btn_apply_max_loss.clicked.connect(self._on_apply_max_loss)
        grid.addWidget(btn_apply_max_loss, 1, 2, 1, 2)

        # Row 2: 按比例吃码 / 按比例上报
        grid.addWidget(QLabel("按比例分配 (%):"), 2, 0)
        self.spin_percent = QDoubleSpinBox()
        self.spin_percent.setRange(0.0, 100.0)
        self.spin_percent.setDecimals(1)
        self.spin_percent.setValue(50.0)
        self.spin_percent.setSuffix(" %")
        grid.addWidget(self.spin_percent, 2, 1)

        btn_pct_eat = QPushButton("按此比例吃码")
        btn_pct_eat.clicked.connect(self._on_apply_pct_eat)
        grid.addWidget(btn_pct_eat, 2, 2)

        btn_pct_rep = QPushButton("按此比例上报")
        btn_pct_rep.clicked.connect(self._on_apply_pct_report)
        grid.addWidget(btn_pct_rep, 2, 3)

        # Row 3: 按指定号码/生肖属性吃码或上报
        grid.addWidget(QLabel("指定号/肖/属性:"), 3, 0)
        self.edit_custom_target = QLineEdit()
        self.edit_custom_target.setPlaceholderText("如: 马,龙,红单 或 08,18,28")
        grid.addWidget(self.edit_custom_target, 3, 1)

        self.spin_custom_amt = QDoubleSpinBox()
        self.spin_custom_amt.setRange(0.0, 10000000.0)
        self.spin_custom_amt.setDecimals(0)
        self.spin_custom_amt.setPrefix("金额: ")
        grid.addWidget(self.spin_custom_amt, 3, 2)

        custom_btn_box = QHBoxLayout()
        btn_custom_eat = QPushButton("设为吃码")
        btn_custom_eat.clicked.connect(lambda: self._on_apply_custom_target("eat"))
        btn_custom_rep = QPushButton("设为上报")
        btn_custom_rep.clicked.connect(lambda: self._on_apply_custom_target("report"))
        custom_btn_box.addWidget(btn_custom_eat)
        custom_btn_box.addWidget(btn_custom_rep)
        grid.addLayout(custom_btn_box, 3, 3)

        calc_layout.addLayout(grid)
        right_layout.addWidget(calc_card)

        # --- 卡片 2: 一键复制散码与格式控制 ---
        copy_card = QFrame()
        copy_card.setProperty("card", True)
        copy_layout = QVBoxLayout(copy_card)
        copy_layout.setContentsMargins(12, 10, 12, 10)
        copy_layout.setSpacing(6)

        copy_header = QHBoxLayout()
        lbl_copy = QLabel("📋 飞单散码格式化与一键复制")
        lbl_copy.setProperty("sectionTitle", True)
        copy_header.addWidget(lbl_copy)
        copy_header.addStretch()

        copy_header.addWidget(QLabel("分隔符:"))
        self.cmb_copy_fmt = QComboBox()
        self.cmb_copy_fmt.addItems([CopyFormat.SPACE.value, CopyFormat.COMMA.value])
        self.cmb_copy_fmt.currentIndexChanged.connect(self._update_copy_preview)
        copy_header.addWidget(self.cmb_copy_fmt)

        copy_header.addWidget(QLabel("金额增减(%):"))
        self.spin_inc_pct = QDoubleSpinBox()
        self.spin_inc_pct.setRange(-90.0, 500.0)
        self.spin_inc_pct.setDecimals(1)
        self.spin_inc_pct.setValue(0.0)
        self.spin_inc_pct.setSuffix(" %")
        self.spin_inc_pct.valueChanged.connect(self._update_copy_preview)
        copy_header.addWidget(self.spin_inc_pct)
        copy_layout.addLayout(copy_header)

        copy_btns = QHBoxLayout()
        self.cmb_copy_type = QComboBox()
        self.cmb_copy_type.addItems(["上报", "吃码", "汇总", "已经上报"])
        self.cmb_copy_type.currentIndexChanged.connect(self._update_copy_preview)
        copy_btns.addWidget(QLabel("预览类型:"))
        copy_btns.addWidget(self.cmb_copy_type)

        for dtype, label, is_primary in [
            ("上报", "📤 复制[预备上报]", True),
            ("吃码", "📥 复制[自己吃码]", False),
            ("汇总", "📊 复制[总汇总]", False),
            ("已经上报", "✅ 复制[已经上报]", False),
        ]:
            btn = QPushButton(label)
            if is_primary:
                btn.setProperty("primary", True)
            btn.clicked.connect(lambda checked, dt=dtype: self._copy_specific_type(dt))
            copy_btns.addWidget(btn)
        copy_layout.addLayout(copy_btns)

        self.txt_copy_preview = QPlainTextEdit()
        self.txt_copy_preview.setMaximumHeight(95)
        self.txt_copy_preview.setReadOnly(True)
        copy_layout.addWidget(self.txt_copy_preview)

        right_layout.addWidget(copy_card)

        # --- 卡片 3: 多上庄飞单提交、撤回与快照中心 ---
        bm_card = QFrame()
        bm_card.setProperty("card", True)
        bm_layout = QVBoxLayout(bm_card)
        bm_layout.setContentsMargins(12, 10, 12, 10)
        bm_layout.setSpacing(6)

        bm_top = QHBoxLayout()
        lbl_bm = QLabel("🏦 上庄报单存档与撤回中心 (上庄张~上庄吴)")
        lbl_bm.setProperty("sectionTitle", True)
        bm_top.addWidget(lbl_bm)
        bm_top.addStretch()

        btn_save_snap = QPushButton("📸 保存风控快照")
        btn_save_snap.clicked.connect(self._on_save_snapshot)
        bm_top.addWidget(btn_save_snap)

        btn_view_snap = QPushButton("📂 查看历史快照")
        btn_view_snap.clicked.connect(self._on_view_snapshots)
        bm_top.addWidget(btn_view_snap)
        bm_layout.addLayout(bm_top)

        bm_ctrl = QHBoxLayout()
        bm_ctrl.addWidget(QLabel("选择上庄:"))
        self.cmb_bookmaker = QComboBox()
        self.cmb_bookmaker.setMinimumWidth(120)
        self.cmb_bookmaker.currentIndexChanged.connect(self._refresh_bookmaker_text)
        bm_ctrl.addWidget(self.cmb_bookmaker)

        btn_rename_bm = QPushButton("重命名上庄")
        btn_rename_bm.clicked.connect(self._on_rename_bookmaker)
        bm_ctrl.addWidget(btn_rename_bm)

        btn_submit_bm = QPushButton("✅ 保存预备上报至该上庄")
        btn_submit_bm.setProperty("success", True)
        btn_submit_bm.clicked.connect(self._on_submit_to_bookmaker)
        bm_ctrl.addWidget(btn_submit_bm)

        btn_withdraw_cur = QPushButton("↩️ 撤回该上庄上报")
        btn_withdraw_cur.setProperty("warning", True)
        btn_withdraw_cur.clicked.connect(self._on_withdraw_current_bookmaker)
        bm_ctrl.addWidget(btn_withdraw_cur)

        btn_withdraw_all = QPushButton("🚨 撤回全部上庄")
        btn_withdraw_all.setProperty("danger", True)
        btn_withdraw_all.clicked.connect(self._on_withdraw_all_bookmakers)
        bm_ctrl.addWidget(btn_withdraw_all)

        bm_layout.addLayout(bm_ctrl)

        self.txt_bookmaker_log = QPlainTextEdit()
        self.txt_bookmaker_log.setPlaceholderText("当前上庄暂无已保存的上报记录...")
        bm_layout.addWidget(self.txt_bookmaker_log, 1)

        right_layout.addWidget(bm_card, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 11)
        splitter.setStretchFactor(1, 10)
        root_layout.addWidget(splitter, 1)

    def refresh_data(self) -> None:
        region = self.controller.current_region
        items = self.controller.risk_service.get_region_risk_items(region)

        # 更新滑块上限
        max_avail = max((it.remaining_pool for it in items), default=0.0)
        self._updating_slider = True
        self.slider_eat.setMaximum(max(100, int(max_avail)))
        self._updating_slider = False

        # 排序
        sorted_items = self._sort_items(items)
        self._populate_table(sorted_items)

        # 更新汇总条
        tot_bet = round(sum(it.total_bet for it in items), 2)
        tot_eat = round(sum(it.eat_amount for it in items), 2)
        tot_rep = round(sum(it.report_amount for it in items), 2)
        tot_reported = round(sum(it.reported_amount for it in items), 2)
        worst_eat_risk = min((it.eat_risk_value for it in items), default=0.0)

        self.lbl_summary_bar.setText(
            f"📊 [{region}] 总收单: {tot_bet:g}  |  自己吃码: {tot_eat:g}  |  "
            f"预备上报: {tot_rep:g}  |  已经上报: {tot_reported:g}  |  "
            f"吃码最差风险值: {worst_eat_risk:+.2f}"
        )

        # 刷新上庄下拉框
        bms = self.controller.risk_service.ensure_bookmakers(region)
        cur_bm = self.cmb_bookmaker.currentText()
        self.cmb_bookmaker.blockSignals(True)
        self.cmb_bookmaker.clear()
        for bm in bms:
            self.cmb_bookmaker.addItem(bm.name)
        idx = self.cmb_bookmaker.findText(cur_bm)
        self.cmb_bookmaker.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_bookmaker.blockSignals(False)

        self._refresh_bookmaker_text()
        self._update_copy_preview()

    def _sort_items(self, items: List[RiskItem]) -> List[RiskItem]:
        idx = self.cmb_sort.currentIndex()
        if idx == 0:
            return sorted(items, key=lambda x: (-x.total_bet, x.full_risk_value, x.number))
        elif idx == 1:
            return sorted(items, key=lambda x: (x.eat_risk_value, -x.eat_amount, x.number))
        elif idx == 2:
            return sorted(items, key=lambda x: (-x.report_amount, x.number))
        return sorted(items, key=lambda x: x.number)

    def _populate_table(self, items: List[RiskItem]) -> None:
        is_dark = self.controller.app_config.theme_mode == "dark"
        self.risk_table.setRowCount(len(items))
        bold_font = QFont("Microsoft YaHei UI", 9, QFont.Bold)

        for r_idx, it in enumerate(items):
            num_item = QTableWidgetItem(f"{it.number:02d}")
            num_item.setIcon(CartoonIconManager.get_icon(f"ball_{it.wave_color}"))
            num_item.setData(Qt.UserRole, it.number)
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFont(bold_font)
            num_item.setForeground(QColor(ThemeManager.get_wave_color_hex(it.wave_color, is_dark)))
            num_item.setBackground(QColor(ThemeManager.get_wave_bg_hex(it.wave_color, is_dark)))
            self.risk_table.setItem(r_idx, 0, num_item)

            zod_item = QTableWidgetItem(it.zodiac)
            zod_item.setIcon(CartoonIconManager.get_icon(f"zodiac_{it.zodiac}"))
            zod_item.setTextAlignment(Qt.AlignCenter)
            self.risk_table.setItem(r_idx, 1, zod_item)

            for col, val in [
                (2, it.total_bet),
                (3, it.eat_amount),
                (4, it.report_amount),
                (5, it.reported_amount),
            ]:
                cell = QTableWidgetItem(f"{val:g}" if val > 0 else "0")
                cell.setTextAlignment(Qt.AlignCenter)
                if col == 3 and val > 0:
                    cell.setFont(bold_font)
                    cell.setForeground(QColor("#2563eb" if not is_dark else "#60a5fa"))
                elif col == 4 and val > 0:
                    cell.setFont(bold_font)
                    cell.setForeground(QColor("#d97706" if not is_dark else "#fbbf24"))
                self.risk_table.setItem(r_idx, col, cell)

            for col, r_val in [(6, it.full_risk_value), (7, it.eat_risk_value)]:
                rcell = QTableWidgetItem(f"{r_val:+.2f}")
                rcell.setTextAlignment(Qt.AlignCenter)
                rcell.setFont(bold_font)
                rcell.setForeground(QColor(ThemeManager.get_pnl_color_hex(r_val, is_dark)))
                self.risk_table.setItem(r_idx, col, rcell)

    def _on_sort_changed(self) -> None:
        self.refresh_data()

    def _on_slider_changed(self, value: int) -> None:
        if self._updating_slider:
            return
        self.spin_avg_eat.setValue(float(value))
        self.controller.risk_service.apply_average_eat(self.controller.current_region, float(value))
        self.refresh_data()
        self.data_changed.emit()

    def _on_apply_avg_eat(self) -> None:
        cap = self.spin_avg_eat.value()
        self._updating_slider = True
        self.slider_eat.setValue(min(self.slider_eat.maximum(), int(cap)))
        self._updating_slider = False
        self.controller.risk_service.apply_average_eat(self.controller.current_region, cap)
        self.refresh_data()
        self.data_changed.emit()

    def _on_apply_max_loss(self) -> None:
        max_loss = self.spin_max_loss.value()
        optimal_cap, _ = self.controller.risk_service.apply_max_loss_eat(
            self.controller.current_region, max_loss
        )
        self.spin_avg_eat.setValue(optimal_cap)
        self._updating_slider = True
        self.slider_eat.setValue(min(self.slider_eat.maximum(), int(optimal_cap)))
        self._updating_slider = False
        self.refresh_data()
        self.data_changed.emit()
        QMessageBox.information(
            self,
            "二分反推完成",
            f"已根据最大允许亏损 [{max_loss:g}] 自动二分计算出最佳单号吃码上限：{optimal_cap:g} 元！",
        )

    def _on_apply_pct_eat(self) -> None:
        pct = self.spin_percent.value()
        self.controller.risk_service.apply_percentage_eat(self.controller.current_region, pct)
        self.refresh_data()
        self.data_changed.emit()

    def _on_apply_pct_report(self) -> None:
        pct = self.spin_percent.value()
        self.controller.risk_service.apply_percentage_report(self.controller.current_region, pct)
        self.refresh_data()
        self.data_changed.emit()

    def _on_apply_custom_target(self, mode: str) -> None:
        expr = self.edit_custom_target.text().strip()
        if not expr:
            QMessageBox.warning(self, "提示", "请输入目标号码、生肖或属性名称（例如：马,龙 或 08,18,28）！")
            return

        tokens = [t.strip() for t in expr.replace("，", ",").replace(" ", ",").split(",") if t.strip()]
        target_nums = set()
        for tok in tokens:
            if tok.isdigit():
                n = int(tok)
                if 1 <= n <= 49:
                    target_nums.add(n)
            else:
                matched = self.controller.attr_engine.get_numbers_by_tag(tok)
                if not matched and len(tok) == 1:
                    matched = self.controller.attr_engine.get_numbers_by_tag(tok + "肖")
                target_nums.update(matched)

        if not target_nums:
            QMessageBox.warning(self, "未匹配到号码", f"未能从「{expr}」解析出任何有效号码，请检查输入！")
            return

        amt = self.spin_custom_amt.value()
        self.controller.risk_service.apply_numbers_eat_or_report(
            self.controller.current_region, sorted(target_nums), amt, mode=mode
        )
        self.refresh_data()
        self.data_changed.emit()

    def _on_table_double_clicked(self, row: int, _col: int) -> None:
        num_item = self.risk_table.item(row, 0)
        if not num_item:
            return
        number = int(num_item.data(Qt.UserRole))
        cur_eat_str = self.risk_table.item(row, 3).text()
        cur_eat = float(cur_eat_str) if cur_eat_str else 0.0
        val, ok = QInputDialog.getDouble(
            self,
            f"修改 {number:02d} 号吃码金额",
            f"请输入 {number:02d} 号的自己吃码金额（超出部分自动归入预备上报）：",
            cur_eat,
            0.0,
            10000000.0,
            2,
        )
        if ok:
            self.controller.risk_service.update_single_number_eat(
                self.controller.current_region, number, val
            )
            self.refresh_data()
            self.data_changed.emit()

    def _on_edit_selected_eat(self) -> None:
        row = self.risk_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先在左侧表格中选择或双击要修改的号码行！")
            return
        self._on_table_double_clicked(row, 3)

    def _on_clear_all_eat(self) -> None:
        self.controller.risk_service.clear_all_eat(self.controller.current_region)
        self.refresh_data()
        self.data_changed.emit()

    def _get_current_copy_format(self) -> CopyFormat:
        return (
            CopyFormat.COMMA
            if self.cmb_copy_fmt.currentText() == CopyFormat.COMMA.value
            else CopyFormat.SPACE
        )

    def _update_copy_preview(self) -> None:
        dtype = self.cmb_copy_type.currentText()
        fmt = self._get_current_copy_format()
        inc = self.spin_inc_pct.value()
        txt = self.controller.risk_service.format_copy_text(
            self.controller.current_region,
            data_type=dtype,
            copy_format=fmt,
            increase_percent=inc,
        )
        self.txt_copy_preview.setPlainText(txt)

    def _copy_specific_type(self, dtype: str) -> None:
        idx = self.cmb_copy_type.findText(dtype)
        if idx >= 0:
            self.cmb_copy_type.setCurrentIndex(idx)
        self._update_copy_preview()
        txt = self.txt_copy_preview.toPlainText()
        QApplication.clipboard().setText(txt)
        QMessageBox.information(self, "已复制到剪贴板", f"【{dtype}】散码数据已复制到剪贴板，可直接粘贴发送！")

    def _refresh_bookmaker_text(self) -> None:
        bm_name = self.cmb_bookmaker.currentText()
        if not bm_name:
            self.txt_bookmaker_log.clear()
            return
        bms = self.controller.risk_service.ensure_bookmakers(self.controller.current_region)
        found = next((b for b in bms if b.name == bm_name), None)
        self.txt_bookmaker_log.setPlainText(found.report_text if found else "")

    def _on_rename_bookmaker(self) -> None:
        old_name = self.cmb_bookmaker.currentText()
        if not old_name:
            return
        new_name, ok = QInputDialog.getText(
            self, "重命名上庄", f"将「{old_name}」重命名为：", text=old_name
        )
        if ok and new_name.strip():
            if self.controller.eat_repo.rename_bookmaker(
                self.controller.current_region, old_name, new_name.strip()
            ):
                self.refresh_data()
            else:
                QMessageBox.warning(self, "重命名失败", "名称为空或与现有上庄重名！")

    def _on_submit_to_bookmaker(self) -> None:
        bm_name = self.cmb_bookmaker.currentText()
        if not bm_name:
            return
        bm = self.controller.risk_service.submit_report_to_bookmaker(
            self.controller.current_region, bm_name
        )
        self.refresh_data()
        self.data_changed.emit()
        QApplication.clipboard().setText(bm.report_text)
        QMessageBox.information(
            self,
            "上报存档成功",
            f"已将预备上报数据正式归档至【{bm_name}】并转入「已经上报」池！\n同时已将上报汇总复制到剪贴板。",
        )

    def _on_withdraw_current_bookmaker(self) -> None:
        bm_name = self.cmb_bookmaker.currentText()
        if not bm_name:
            return
        reply = QMessageBox.question(
            self,
            "确认撤回",
            f"确定要撤回【{bm_name}】的全部已上报数据并退回至「预备上报」吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.controller.risk_service.withdraw_bookmaker_report(
                self.controller.current_region, bm_name
            )
            self.refresh_data()
            self.data_changed.emit()

    def _on_withdraw_all_bookmakers(self) -> None:
        reply = QMessageBox.question(
            self,
            "确认全部撤回",
            "确定要撤回当前盘口所有上庄的全部已上报数据吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.controller.risk_service.withdraw_all_bookmakers_reports(
                self.controller.current_region
            )
            self.refresh_data()
            self.data_changed.emit()

    def _on_save_snapshot(self) -> None:
        region = self.controller.current_region
        title, ok = QInputDialog.getText(
            self, "保存风控快照", "请输入本次快照备注名称：", text=f"{region}_风控快照"
        )
        if not ok or not title.strip():
            return
        items = self.controller.risk_service.get_region_risk_items(region)
        rows = [
            {
                "number": it.number,
                "zodiac": it.zodiac,
                "total_bet": it.total_bet,
                "eat_amount": it.eat_amount,
                "report_amount": it.report_amount,
                "reported_amount": it.reported_amount,
                "eat_risk_value": it.eat_risk_value,
            }
            for it in items
        ]
        self.controller.eat_repo.save_snapshot(region, title.strip(), rows)
        QMessageBox.information(self, "保存成功", "当前吃码与上报风控快照已保存至本地数据库！")

    def _on_view_snapshots(self) -> None:
        dlg = SnapshotViewerDialog(self.controller, self)
        dlg.exec_()
