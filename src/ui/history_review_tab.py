"""
Tab 5: 历史日期回看与复盘中心 (HistoryReviewTab)

- 支持「今天 / 昨天 / 近7天 / 近30天 / 本月 / 全部日期」快捷区间与自定义起止日期；
- 同时回看当前活动订单与「清空本盘」前自动归档的历史账目；
- 支持「模拟特码」对历史区间重新对奖推演（只读，不改动原始账目）；
- 提供订单流水、按日趋势、期数归档库、分人算账、1-49 号码复盘五大视图；
- 支持一键归档、恢复归档、删除归档、复制历史结账单与导出历史 Excel。
"""

from __future__ import annotations

from datetime import date
from typing import Callable, List, Optional

from PyQt5.QtCore import QDate, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.domain.models import DailyArchiveRecord, DateRangeReviewSummary, OrderRecord
from src.services.app_controller import ApplicationController
from src.services.history_review_service import ALL_CLIENTS, ALL_REGIONS
from src.ui.icon_manager import CartoonIconManager
from src.ui.styles import ThemeManager

CURRENT_REGION_LABEL = "当前盘口"
WAVE_CN = {"red": "红波", "blue": "蓝波", "green": "绿波"}


class HistoryReviewTab(QWidget):
    """按日期历史回看与复盘标签页"""

    data_changed = pyqtSignal()

    def __init__(
        self,
        controller: ApplicationController,
        on_data_changed: Optional[Callable[[], None]] = None,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._on_data_changed = on_data_changed
        self.summary: Optional[DateRangeReviewSummary] = None
        self._displayed_orders: List[OrderRecord] = []
        self._archives: List[DailyArchiveRecord] = []
        self._init_ui()
        self.set_quick_range("今天", run_query=False)
        self.refresh_data()

    # ==================================================================
    # UI 构建
    # ==================================================================
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ---------- 第一行：快捷区间 + 已有日期 + 起止日期 ----------
        filter_card = QFrame()
        filter_card.setProperty("card", True)
        f_layout = QVBoxLayout(filter_card)
        f_layout.setContentsMargins(14, 10, 14, 10)
        f_layout.setSpacing(8)

        row1 = QHBoxLayout()
        title = QLabel("📅 按日期历史回看:")
        title.setProperty("sectionTitle", True)
        row1.addWidget(title)

        self.quick_buttons = {}
        for preset in ("今天", "昨天", "近7天", "近30天", "本月", "全部日期"):
            btn = QPushButton(preset)
            btn.setMinimumWidth(64)
            btn.clicked.connect(lambda _c=False, p=preset: self.set_quick_range(p))
            self.quick_buttons[preset] = btn
            row1.addWidget(btn)

        row1.addSpacing(10)
        row1.addWidget(QLabel("有账日期:"))
        self.cmb_known_dates = QComboBox()
        self.cmb_known_dates.setMinimumWidth(150)
        self.cmb_known_dates.setToolTip("列出所有存在订单或归档记录的日期，选择后直接回看该日")
        self.cmb_known_dates.activated.connect(self._on_known_date_selected)
        row1.addWidget(self.cmb_known_dates)

        row1.addSpacing(10)
        row1.addWidget(QLabel("从"))
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        row1.addWidget(self.date_start)
        row1.addWidget(QLabel("至"))
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        row1.addWidget(self.date_end)
        row1.addStretch()
        f_layout.addLayout(row1)

        # ---------- 第二行：盘口 / 客户 / 模拟特码 / 动作按钮 ----------
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("盘口:"))
        self.cmb_region = QComboBox()
        self.cmb_region.setMinimumWidth(110)
        self.cmb_region.currentIndexChanged.connect(self._on_region_filter_changed)
        row2.addWidget(self.cmb_region)

        row2.addWidget(QLabel("客户:"))
        self.cmb_client = QComboBox()
        self.cmb_client.setMinimumWidth(110)
        row2.addWidget(self.cmb_client)

        row2.addWidget(QLabel("对奖口径:"))
        self.cmb_sim_win = QComboBox()
        self.cmb_sim_win.setMinimumWidth(170)
        self.cmb_sim_win.addItem(CartoonIconManager.get_icon("act_settle"), "按原单记录", 0)
        for num in range(1, 50):
            wave = self.controller.attr_engine.get_wave_color(num)
            zod = self.controller.attr_engine.get_zodiac_of_number(num)
            self.cmb_sim_win.addItem(
                CartoonIconManager.get_icon(f"ball_{wave}"), f"模拟特码 {num:02d} [{zod}·{WAVE_CN.get(wave, '')}]", num
            )
        row2.addWidget(self.cmb_sim_win)

        self.btn_query = QPushButton("🔍 查询回看")
        self.btn_query.setProperty("primary", True)
        self.btn_query.clicked.connect(self.run_query)
        row2.addWidget(self.btn_query)

        row2.addStretch()

        self.btn_archive = QPushButton("📥 归档当前盘口账目")
        self.btn_archive.setToolTip("将当前盘口全部订单与算账结果保存为一条历史快照（不会清空当前盘口）")
        self.btn_archive.clicked.connect(self._on_archive_current)
        row2.addWidget(self.btn_archive)

        self.btn_export = QPushButton("📊 导出历史 Excel")
        self.btn_export.setProperty("success", True)
        self.btn_export.clicked.connect(self._on_export_excel)
        row2.addWidget(self.btn_export)

        self.btn_copy_bill = QPushButton("📋 复制历史结账单")
        self.btn_copy_bill.clicked.connect(self._on_copy_bill)
        row2.addWidget(self.btn_copy_bill)
        f_layout.addLayout(row2)
        root.addWidget(filter_card)

        # ---------- KPI 卡片 ----------
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        self.kpi_orders = self._make_kpi(kpi_row, "tab_history", "区间订单 / 活跃天数")
        self.kpi_total = self._make_kpi(kpi_row, "kpi_pool", "区间总收单额")
        self.kpi_top = self._make_kpi(kpi_row, "kpi_risk", "区间头号热门码")
        self.kpi_pnl = self._make_kpi(kpi_row, "kpi_profit", "区间庄家净盈亏")
        root.addLayout(kpi_row)

        # ---------- 子标签页 ----------
        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(self._build_orders_page(), "📜 历史订单流水与中码高亮详情")
        self.sub_tabs.addTab(self._build_trend_page(), "📅 按日趋势对比与期数归档库")
        self.sub_tabs.addTab(self._build_client_page(), "👥 历史区间分人算账汇总表")
        self.sub_tabs.addTab(self._build_number_page(), "🎯 历史区间 1-49 号码押注与风险复盘")
        root.addWidget(self.sub_tabs, 1)

    def _make_kpi(self, layout: QHBoxLayout, icon: str, caption: str) -> QLabel:
        card = QFrame()
        card.setProperty("card", True)
        g = QGridLayout(card)
        g.setContentsMargins(12, 8, 12, 8)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(CartoonIconManager.render_pixmap(icon, 36))
        g.addWidget(icon_lbl, 0, 0, 2, 1)
        cap = QLabel(caption)
        cap.setStyleSheet("color: #64748b; font-size: 12px;")
        g.addWidget(cap, 0, 1)
        val = QLabel("-")
        val.setStyleSheet("font-size: 18px; font-weight: bold;")
        g.addWidget(val, 1, 1)
        g.setColumnStretch(1, 1)
        layout.addWidget(card, 1)
        return val

    @staticmethod
    def _make_table(headers: List[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setAlternatingRowColors(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return t

    def _build_orders_page(self) -> QWidget:
        page = QSplitter(Qt.Horizontal)
        left = QFrame()
        left.setProperty("card", True)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 8, 10, 8)
        bar = QHBoxLayout()
        self.lbl_orders_title = QLabel("历史订单流水")
        self.lbl_orders_title.setProperty("sectionTitle", True)
        bar.addWidget(self.lbl_orders_title)
        bar.addStretch()
        self.edit_keyword = QLineEdit()
        self.edit_keyword.setPlaceholderText("在结果中搜索原内容 / 号码 / 客户...")
        self.edit_keyword.setMaximumWidth(240)
        self.edit_keyword.textChanged.connect(self._refresh_orders_table)
        bar.addWidget(self.edit_keyword)
        lv.addLayout(bar)

        self.order_table = self._make_table(
            ["下单时间", "盘口", "客户", "原内容摘要", "识别后押注内容", "下单额", "中码金额", "回水", "净盈亏"]
        )
        self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.order_table.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate([140, 70, 80, 170, 230, 70, 75, 70, 85]):
            self.order_table.setColumnWidth(i, w)
        self.order_table.itemSelectionChanged.connect(self._on_order_selected)
        lv.addWidget(self.order_table, 1)
        page.addWidget(left)

        right = QFrame()
        right.setProperty("card", True)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 8, 10, 8)
        lbl = QLabel("🔍 订单详情 & 中码高亮")
        lbl.setProperty("sectionTitle", True)
        rv.addWidget(lbl)
        self.browser_detail = QTextBrowser()
        rv.addWidget(self.browser_detail, 1)
        page.addWidget(right)
        page.setStretchFactor(0, 14)
        page.setStretchFactor(1, 6)
        return page

    def _build_trend_page(self) -> QWidget:
        page = QSplitter(Qt.Horizontal)

        left = QFrame()
        left.setProperty("card", True)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 8, 10, 8)
        lbl = QLabel("📈 按日趋势对比（双击某天可单独回看当天）")
        lbl.setProperty("sectionTitle", True)
        lv.addWidget(lbl)
        self.trend_table = self._make_table(
            ["日期", "订单数", "客户数", "收单额", "中码赔付", "回水", "庄家净盈亏", "热门码", "热门码押注"]
        )
        self.trend_table.cellDoubleClicked.connect(self._on_trend_double_clicked)
        lv.addWidget(self.trend_table, 1)
        page.addWidget(left)

        right = QFrame()
        right.setProperty("card", True)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 8, 10, 8)
        lbl2 = QLabel("🗂️ 期数归档库（区间内）")
        lbl2.setProperty("sectionTitle", True)
        rv.addWidget(lbl2)
        self.archive_table = self._make_table(["归档日期", "盘口", "标题", "特码", "订单", "收单额", "净盈亏"])
        self.archive_table.cellDoubleClicked.connect(lambda r, _c: self._on_view_archive())
        rv.addWidget(self.archive_table, 1)
        btns = QHBoxLayout()
        self.btn_view_archive = QPushButton("🔍 查看快照")
        self.btn_view_archive.clicked.connect(self._on_view_archive)
        self.btn_restore_archive = QPushButton("🔄 恢复到当前盘口")
        self.btn_restore_archive.clicked.connect(self._on_restore_archive)
        self.btn_delete_archive = QPushButton("🗑️ 删除归档")
        self.btn_delete_archive.setProperty("danger", True)
        self.btn_delete_archive.clicked.connect(self._on_delete_archive)
        for b in (self.btn_view_archive, self.btn_restore_archive, self.btn_delete_archive):
            btns.addWidget(b)
        rv.addLayout(btns)
        page.addWidget(right)
        page.setStretchFactor(0, 12)
        page.setStretchFactor(1, 9)
        return page

    def _build_client_page(self) -> QWidget:
        card = QFrame()
        card.setProperty("card", True)
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 8)
        self.lbl_client_summary = QLabel("")
        self.lbl_client_summary.setStyleSheet("font-weight: bold;")
        v.addWidget(self.lbl_client_summary)
        self.client_table = self._make_table(
            ["客户", "订单笔数", "赔率", "回水比例", "下单总额", "中码金额", "盈亏(不含回水)", "回水金额", "净盈亏(含回水)"]
        )
        v.addWidget(self.client_table, 1)
        return card

    def _build_number_page(self) -> QWidget:
        card = QFrame()
        card.setProperty("card", True)
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 8)
        hint = QLabel("按区间押注额从高到低排列；风险值 = 区间总收单 × (1 - 回水) - 该号押注 × 赔率（负数表示开出该号庄家亏损）")
        hint.setStyleSheet("color: #64748b;")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.number_table = self._make_table(["排名", "号码", "生肖", "波色", "区间押注额", "占比", "风险值(盈亏)"])
        v.addWidget(self.number_table, 1)
        return card

    # ==================================================================
    # 数据刷新
    # ==================================================================
    def refresh_data(self) -> None:
        """主窗口统一刷新入口：更新下拉框并按当前条件重新查询"""
        self._refresh_region_combo()
        self._refresh_client_combo()
        self._refresh_known_dates()
        self.run_query()

    def _selected_region(self) -> Optional[str]:
        text = self.cmb_region.currentText()
        if not text or text == CURRENT_REGION_LABEL:
            return self.controller.current_region
        if text == ALL_REGIONS:
            return None
        return text

    def _refresh_region_combo(self) -> None:
        cur = self.cmb_region.currentText() or CURRENT_REGION_LABEL
        self.cmb_region.blockSignals(True)
        self.cmb_region.clear()
        self.cmb_region.addItem(CURRENT_REGION_LABEL)
        self.cmb_region.addItem(ALL_REGIONS)
        for r in self.controller.region_repo.list_regions():
            self.cmb_region.addItem(r.name)
        idx = self.cmb_region.findText(cur)
        self.cmb_region.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_region.blockSignals(False)

    def _refresh_client_combo(self) -> None:
        cur = self.cmb_client.currentText() or ALL_CLIENTS
        region = self._selected_region()
        names = []
        regions = [region] if region else [r.name for r in self.controller.region_repo.list_regions()]
        for rn in regions:
            for c in self.controller.client_repo.list_clients(rn):
                if c.name not in names:
                    names.append(c.name)
        # 归档中可能存在已删除的老客户，一并列出
        for arc in self.controller.history_service.list_archives(region=region):
            for st in arc.settlements_data:
                n = str(st.get("client_name", ""))
                if n and n not in names:
                    names.append(n)
        self.cmb_client.blockSignals(True)
        self.cmb_client.clear()
        self.cmb_client.addItem(ALL_CLIENTS)
        self.cmb_client.addItems(names)
        idx = self.cmb_client.findText(cur)
        self.cmb_client.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_client.blockSignals(False)

    def _refresh_known_dates(self) -> None:
        dates = self.controller.history_service.get_all_available_dates(self._selected_region())
        self.cmb_known_dates.blockSignals(True)
        self.cmb_known_dates.clear()
        self.cmb_known_dates.addItem(f"共 {len(dates)} 个有账日期", "")
        for d in dates:
            self.cmb_known_dates.addItem(d, d)
        self.cmb_known_dates.blockSignals(False)

    def _on_region_filter_changed(self) -> None:
        self._refresh_client_combo()
        self._refresh_known_dates()

    # ==================================================================
    # 日期操作
    # ==================================================================
    def set_date_range(self, start: str, end: str, run_query: bool = True) -> None:
        self.date_start.setDate(QDate.fromString(start, "yyyy-MM-dd"))
        self.date_end.setDate(QDate.fromString(end, "yyyy-MM-dd"))
        if run_query:
            self.run_query()

    def set_quick_range(self, preset: str, run_query: bool = True) -> None:
        if preset == "全部日期":
            dates = self.controller.history_service.get_all_available_dates(self._selected_region())
            today = date.today().strftime("%Y-%m-%d")
            start, end = (dates[-1], max(dates[0], today)) if dates else (today, today)
        else:
            start, end = self.controller.history_service.quick_range(preset)
        self.set_date_range(start, end, run_query)

    def _on_known_date_selected(self, idx: int) -> None:
        d = self.cmb_known_dates.itemData(idx)
        if d:
            self.set_date_range(d, d)

    def _on_trend_double_clicked(self, row: int, _col: int) -> None:
        item = self.trend_table.item(row, 0)
        if item and item.text():
            self.set_date_range(item.text(), item.text())
            self.sub_tabs.setCurrentIndex(0)

    # ==================================================================
    # 查询与渲染
    # ==================================================================
    def run_query(self) -> Optional[DateRangeReviewSummary]:
        start = self.date_start.date().toString("yyyy-MM-dd")
        end = self.date_end.date().toString("yyyy-MM-dd")
        if start > end:
            start, end = end, start
            self.set_date_range(start, end, run_query=False)
        region = self._selected_region()
        client = self.cmb_client.currentText() or ALL_CLIENTS
        sim = int(self.cmb_sim_win.currentData() or 0)

        self.summary = self.controller.history_service.query_date_range_review(
            start, end, region=region, client_filter=client, simulated_winning_number=sim
        )
        self._archives = self.controller.history_service.list_archives(start, end, region)
        self._render_kpis()
        self._refresh_orders_table()
        self._render_trends()
        self._render_archives()
        self._render_clients()
        self._render_numbers()
        return self.summary

    def _is_dark(self) -> bool:
        return self.controller.app_config.theme_mode == "dark"

    def _pnl_item(self, value: float, text: Optional[str] = None) -> QTableWidgetItem:
        it = QTableWidgetItem(text if text is not None else f"{value:+.2f}")
        it.setTextAlignment(Qt.AlignCenter)
        it.setFont(QFont("Microsoft YaHei UI", 9, QFont.Bold))
        it.setForeground(QColor(ThemeManager.get_pnl_color_hex(value, self._is_dark())))
        return it

    @staticmethod
    def _cell(text: str, align=Qt.AlignCenter) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setTextAlignment(align)
        return it

    def _render_kpis(self) -> None:
        s = self.summary
        if not s:
            return
        self.kpi_orders.setText(f"{s.total_orders} 笔 / {s.active_days_count} 天")
        self.kpi_total.setText(f"¥ {s.total_bet:g}")
        if s.top_number:
            zod = self.controller.attr_engine.get_zodiac_of_number(s.top_number)
            self.kpi_top.setText(f"{s.top_number:02d} 号 [{zod}] ¥{s.top_number_bet:g}")
        else:
            self.kpi_top.setText("-")
        self.kpi_pnl.setText(f"{s.total_net_pnl:+.2f}")
        self.kpi_pnl.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {ThemeManager.get_pnl_color_hex(s.total_net_pnl, self._is_dark())};"
        )

    def _refresh_orders_table(self) -> None:
        if not self.summary:
            return
        kw = self.edit_keyword.text().strip()
        orders = self.summary.orders
        if kw:
            orders = [o for o in orders if kw in o.raw_text or kw in o.parsed_content or kw in o.client_name]
        self._displayed_orders = orders
        s = self.summary
        label = s.start_date if s.start_date == s.end_date else f"{s.start_date} ~ {s.end_date}"
        mode = f"模拟特码 {s.simulated_winning_number:02d}" if s.simulated_winning_number else "按原单记录"
        self.lbl_orders_title.setText(f"📜 {label} 历史订单流水（{len(orders)} 笔 · {mode}）")

        self.order_table.setRowCount(len(orders))
        for r, o in enumerate(orders):
            vals = [
                o.created_at, o.region, o.client_name, o.raw_text.replace("\n", " ↵ "),
                o.parsed_content.replace("\n", " | "), f"{o.total_amount:g}", f"{o.winning_amount:g}",
                f"{o.rebate_amount:+.2f}",
            ]
            for c, v in enumerate(vals):
                align = Qt.AlignLeft | Qt.AlignVCenter if c in (3, 4) else Qt.AlignCenter
                cell = self._cell(v, align)
                if c == 6 and o.winning_amount > 0:
                    cell.setForeground(QColor("#dc2626"))
                    cell.setFont(QFont("Microsoft YaHei UI", 9, QFont.Bold))
                self.order_table.setItem(r, c, cell)
            self.order_table.setItem(r, 8, self._pnl_item(o.net_pnl))
        if orders:
            self.order_table.selectRow(0)
        else:
            self.browser_detail.setHtml("<p style='color:gray;'>所选日期区间内暂无订单记录。</p>")

    def _effective_win_number(self, order: OrderRecord) -> int:
        if self.summary and self.summary.simulated_winning_number:
            return self.summary.simulated_winning_number
        if order.winning_amount > 0:
            reg = self.controller.region_repo.get_region(order.region)
            if reg and 1 <= reg.last_winning_number <= 49:
                return reg.last_winning_number
            for arc in self._archives:
                if arc.region == order.region and arc.winning_number:
                    return arc.winning_number
        return 0

    def _on_order_selected(self) -> None:
        row = self.order_table.currentRow()
        if row < 0 or row >= len(self._displayed_orders):
            return
        o = self._displayed_orders[row]
        win = self._effective_win_number(o)
        hl = self.controller.settlement_service.highlight_winning_number_html(o.parsed_content, win)
        raw = o.raw_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        win_txt = f"<span style='color:#dc2626;font-weight:bold;'>{win:02d} 号</span>" if win else "未开奖 / 未中码"
        self.browser_detail.setHtml(
            f"""
            <div style="font-family:'Microsoft YaHei UI'; font-size:13px; line-height:1.5;">
              <p><b>下单时间：</b>{o.created_at}</p>
              <p><b>盘口：</b>{o.region} &nbsp; <b>客户：</b>{o.client_name}</p>
              <p><b>下单额：</b>{o.total_amount:g} 元 &nbsp; <b>中码：</b>{o.winning_amount:g} 元</p>
              <p><b>特码：</b>{win_txt} &nbsp; <b>净盈亏：</b>{o.net_pnl:+.2f} 元</p>
              <hr><p><b>【原始消息】</b></p>
              <div style="background:rgba(148,163,184,0.12); padding:8px; border-radius:6px;">{raw}</div>
              <p><b>【标准押注内容（中码红色高亮）】</b></p>
              <div style="background:rgba(37,99,235,0.08); padding:8px; border-radius:6px;">{hl}</div>
            </div>
            """
        )

    def _render_trends(self) -> None:
        trends = self.summary.daily_trends if self.summary else []
        self.trend_table.setRowCount(len(trends))
        for r, t in enumerate(trends):
            vals = [t.date_str, str(t.order_count), str(t.client_count), f"{t.total_bet:g}",
                    f"{t.winning_payout:g}", f"{t.rebate_amount:+.2f}"]
            for c, v in enumerate(vals):
                self.trend_table.setItem(r, c, self._cell(v))
            self.trend_table.setItem(r, 6, self._pnl_item(t.net_pnl))
            self.trend_table.setItem(r, 7, self._cell(f"{t.top_number:02d}" if t.top_number else "-"))
            self.trend_table.setItem(r, 8, self._cell(f"{t.top_number_bet:g}"))

    def _render_archives(self) -> None:
        self.archive_table.setRowCount(len(self._archives))
        for r, a in enumerate(self._archives):
            vals = [a.archive_date, a.region, a.title, f"{a.winning_number:02d}" if a.winning_number else "-",
                    str(a.order_count), f"{a.total_bet:g}"]
            for c, v in enumerate(vals):
                cell = self._cell(v)
                if c == 0:
                    cell.setData(Qt.UserRole, a.id)
                self.archive_table.setItem(r, c, cell)
            self.archive_table.setItem(r, 6, self._pnl_item(a.net_pnl))

    def _render_clients(self) -> None:
        s = self.summary
        items = s.client_settlements if s else []
        self.client_table.setRowCount(len(items))
        for r, st in enumerate(items):
            vals = [st.client_name, str(st.order_count), f"{st.odds:g}", f"{st.rebate * 100:.1f}%",
                    f"{st.total_bet:g}", f"{st.winning_bet:g}"]
            for c, v in enumerate(vals):
                self.client_table.setItem(r, c, self._cell(v))
            self.client_table.setItem(r, 6, self._pnl_item(st.pnl_no_rebate))
            self.client_table.setItem(r, 7, self._cell(f"{st.rebate_amount:+.2f}"))
            self.client_table.setItem(r, 8, self._pnl_item(st.net_pnl))
        if s:
            self.lbl_client_summary.setText(
                f"📌 {len(items)} 位客户 | 总收单 {s.total_bet:g} 元 | 中码赔付 {s.total_winning_payout:g} 元 | "
                f"回水 {s.total_rebate:+.2f} 元 | 庄家净盈亏 {s.total_net_pnl:+.2f} 元"
            )

    def _render_numbers(self) -> None:
        s = self.summary
        items = sorted(s.risk_items, key=lambda it: (-it.total_bet, it.number)) if s else []
        pool = s.total_bet if s else 0.0
        num_pool = sum(it.total_bet for it in items) or 0.0
        self.number_table.setRowCount(len(items))
        for r, it in enumerate(items):
            ratio = f"{it.total_bet / num_pool * 100:.1f}%" if num_pool > 0 else "-"
            vals = [str(r + 1), it.number_str, it.zodiac, WAVE_CN.get(it.wave_color, ""), f"{it.total_bet:g}", ratio]
            for c, v in enumerate(vals):
                cell = self._cell(v)
                if c == 1:
                    cell.setIcon(CartoonIconManager.get_icon(f"ball_{it.wave_color}"))
                self.number_table.setItem(r, c, cell)
            self.number_table.setItem(r, 6, self._pnl_item(it.full_risk_value))
        _ = pool

    # ==================================================================
    # 动作：归档 / 恢复 / 删除 / 导出 / 复制
    # ==================================================================
    def _notify_changed(self) -> None:
        self.data_changed.emit()
        if self._on_data_changed:
            self._on_data_changed()

    def _selected_archive(self) -> Optional[DailyArchiveRecord]:
        row = self.archive_table.currentRow()
        if row < 0 or row >= len(self._archives):
            QMessageBox.information(self, "提示", "请先在右侧期数归档库中选择一条归档记录！")
            return None
        return self._archives[row]

    def archive_current(self, title: str = "") -> Optional[DailyArchiveRecord]:
        """归档当前盘口（供按钮与测试调用）"""
        rec = self.controller.history_service.archive_current_region_session(
            self.controller.current_region, custom_title=title
        )
        self.refresh_data()
        return rec

    def _on_archive_current(self) -> None:
        rec = self.archive_current()
        if rec:
            QMessageBox.information(
                self, "归档成功",
                f"已归档【{rec.region}】{rec.archive_date} 共 {rec.order_count} 笔订单（{rec.title}）。\n当前盘口数据保持不变。",
            )
        else:
            QMessageBox.information(self, "无需归档", "当前盘口暂无订单，无需归档。")

    def _on_view_archive(self) -> None:
        arc = self._selected_archive()
        if not arc:
            return
        self.cmb_region.setCurrentIndex(max(0, self.cmb_region.findText(arc.region)))
        self.cmb_client.setCurrentIndex(0)
        dates = [str(o.get("created_at", ""))[:10] for o in arc.orders_data if o.get("created_at")]
        start = min(dates) if dates else arc.archive_date
        end = max(dates) if dates else arc.archive_date
        self.set_date_range(start, end)
        self.sub_tabs.setCurrentIndex(0)

    def restore_archive(self, archive_id: int) -> int:
        n = self.controller.history_service.restore_archive_to_region(archive_id, self.controller.current_region)
        self.refresh_data()
        if n:
            self._notify_changed()
        return n

    def _on_restore_archive(self) -> None:
        arc = self._selected_archive()
        if not arc:
            return
        target = self.controller.current_region
        reply = QMessageBox.question(
            self, "确认恢复",
            f"确定将归档「{arc.title}」中的 {arc.order_count} 笔订单恢复到当前盘口【{target}】吗？\n已存在的相同订单会自动跳过。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            n = self.restore_archive(arc.id)
            QMessageBox.information(self, "恢复完成", f"已恢复 {n} 笔订单到【{target}】。")

    def _on_delete_archive(self) -> None:
        arc = self._selected_archive()
        if not arc:
            return
        reply = QMessageBox.warning(
            self, "确认删除归档",
            f"确定永久删除归档「{arc.title}」吗？\n若该归档对应的订单已被清空，删除后将无法再回看这些历史！",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes and arc.id is not None:
            self.controller.history_service.delete_archive(arc.id)
            self.refresh_data()

    def export_excel_to(self, path: str):
        if not self.summary:
            self.run_query()
        return self.controller.history_service.export_history_review_to_excel(self.summary, path)

    def _on_export_excel(self) -> None:
        if not self.summary or not self.summary.total_orders:
            QMessageBox.information(self, "提示", "当前日期区间内暂无订单，无需导出。")
            return
        s = self.summary
        default_name = f"历史回看_{s.start_date}_{s.end_date}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "导出历史回看 Excel", default_name, "Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            out = self.export_excel_to(path)
            QMessageBox.information(self, "导出成功", f"历史回看报表已导出：\n{out}")
        except Exception as exc:  # 文件被占用等
            QMessageBox.critical(self, "导出失败", f"导出失败（文件可能正被 Excel 打开）：\n{exc}")

    def build_bill_text(self) -> str:
        if not self.summary:
            self.run_query()
        return self.controller.history_service.format_history_settlement_bill(self.summary)

    def _on_copy_bill(self) -> None:
        QApplication.clipboard().setText(self.build_bill_text())
        QMessageBox.information(self, "已复制", "历史区间结账单已复制到剪贴板！")
