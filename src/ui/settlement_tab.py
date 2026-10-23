"""
Tab 4: 订单明细与开奖对奖算账中心 (SettlementTab)
完整复刻并增强原 Excel `新澳门明细`、`香港明细`、`旧澳门明细`、`明细模块`（双击撤单扣回押注）
与 `分人统计_对奖和算账.frm`（开奖特码对奖、中码高亮、分人盈亏与回水自动核算）功能。
"""

from __future__ import annotations
from typing import List, Optional
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from src.domain.models import ClientSettlementItem, OrderRecord
from src.services.app_controller import ApplicationController
from src.ui.icon_manager import CartoonIconManager
from src.ui.styles import ThemeManager


class SettlementTab(QWidget):
    """订单明细与开奖对奖算账中心标签页"""

    data_changed = pyqtSignal()

    def __init__(self, controller: ApplicationController, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._current_orders: List[OrderRecord] = []
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # ================= 顶部：开奖特码对奖与算账控制栏 =================
        top_card = QFrame()
        top_card.setProperty("card", True)
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(14, 10, 14, 10)
        top_layout.setSpacing(10)

        lbl_prize = QLabel("🏆 特码开奖对奖与算账中心:")
        lbl_prize.setProperty("sectionTitle", True)
        top_layout.addWidget(lbl_prize)

        top_layout.addWidget(QLabel("本期开奖特码:"))
        self.cmb_winning_num = QComboBox()
        self.cmb_winning_num.setMinimumWidth(160)
        self._populate_winning_combo()
        top_layout.addWidget(self.cmb_winning_num)

        btn_settle = QPushButton("🎯 立即对奖并核算全盘盈亏")
        btn_settle.setProperty("primary", True)
        btn_settle.clicked.connect(self._on_run_settlement)
        top_layout.addWidget(btn_settle)

        btn_clear_win = QPushButton("🔄 仅算总账(清除中码)")
        btn_clear_win.clicked.connect(self._on_clear_winning_number)
        top_layout.addWidget(btn_clear_win)

        btn_copy_bill = QPushButton("📋 复制分人结账单")
        btn_copy_bill.setProperty("success", True)
        btn_copy_bill.clicked.connect(self._on_copy_settlement_bill)
        top_layout.addWidget(btn_copy_bill)

        top_layout.addStretch()

        btn_rebuild = QPushButton("🛠️ 重新同步校验押注")
        btn_rebuild.setToolTip("根据订单明细重新校准所有客户 1-49 号押注总额")
        btn_rebuild.clicked.connect(self._on_rebuild_bets)
        top_layout.addWidget(btn_rebuild)

        btn_clear_all = QPushButton("🗑️ 清空本盘全部订单与押注")
        btn_clear_all.setProperty("danger", True)
        btn_clear_all.clicked.connect(self._on_clear_region_all)
        top_layout.addWidget(btn_clear_all)

        root_layout.addWidget(top_card)

        # ================= 主体：上下分栏（上：分人结算总表；下：订单流水台账 + 中码高亮详情） =================
        v_splitter = QSplitter(Qt.Vertical)

        # --- 上半部分：分人统计对奖与算账汇总表 ---
        client_card = QFrame()
        client_card.setProperty("card", True)
        client_layout = QVBoxLayout(client_card)
        client_layout.setContentsMargins(12, 10, 12, 10)
        client_layout.setSpacing(6)

        c_head = QHBoxLayout()
        lbl_c_title = QLabel("👥 分人统计对奖与算账汇总表 (点击客户行可自动筛选下方订单明细)")
        lbl_c_title.setProperty("sectionTitle", True)
        c_head.addWidget(lbl_c_title)
        c_head.addStretch()
        self.lbl_grand_summary = QLabel("")
        self.lbl_grand_summary.setStyleSheet("font-weight: bold; font-size: 13px;")
        c_head.addWidget(self.lbl_grand_summary)
        client_layout.addLayout(c_head)

        self.client_table = QTableWidget(0, 9)
        self.client_table.setHorizontalHeaderLabels([
            "客户名称",
            "订单笔数",
            "特码赔率",
            "回水比例",
            "下单总金额",
            "中码金额",
            "盈亏 (不包回水)",
            "回水金额",
            "庄家净盈亏 (含回水)",
        ])
        self.client_table.verticalHeader().setVisible(False)
        self.client_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.client_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.client_table.setAlternatingRowColors(True)
        self.client_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.client_table.cellClicked.connect(self._on_client_row_clicked)
        client_layout.addWidget(self.client_table, 1)

        v_splitter.addWidget(client_card)

        # --- 下半部分：订单明细流水台账 + 右侧中码红色高亮详情预览 ---
        bottom_splitter = QSplitter(Qt.Horizontal)

        order_card = QFrame()
        order_card.setProperty("card", True)
        order_layout = QVBoxLayout(order_card)
        order_layout.setContentsMargins(12, 10, 12, 10)
        order_layout.setSpacing(6)

        filter_bar = QHBoxLayout()
        lbl_o_title = QLabel("📜 订单明细流水台账 (双击或点击按钮可撤单并自动扣回押注)")
        lbl_o_title.setProperty("sectionTitle", True)
        filter_bar.addWidget(lbl_o_title)
        filter_bar.addStretch()

        filter_bar.addWidget(QLabel("按客户筛选:"))
        self.cmb_client_filter = QComboBox()
        self.cmb_client_filter.setMinimumWidth(120)
        self.cmb_client_filter.currentIndexChanged.connect(self._refresh_orders_table)
        filter_bar.addWidget(self.cmb_client_filter)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("搜索原内容 / 号码 / 客户...")
        self.edit_search.setMaximumWidth(200)
        self.edit_search.textChanged.connect(self._refresh_orders_table)
        filter_bar.addWidget(self.edit_search)

        btn_delete_order = QPushButton("❌ 删除选中订单并扣减押注")
        btn_delete_order.setProperty("danger", True)
        btn_delete_order.clicked.connect(self._on_delete_selected_order)
        filter_bar.addWidget(btn_delete_order)

        order_layout.addLayout(filter_bar)

        self.order_table = QTableWidget(0, 10)
        self.order_table.setHorizontalHeaderLabels([
            "序号",
            "客户",
            "原内容摘要",
            "识别后押注内容",
            "下单总额",
            "中码金额",
            "盈亏(不包回水)",
            "回水金额",
            "净盈亏(含回水)",
            "录入时间",
        ])
        self.order_table.verticalHeader().setVisible(False)
        self.order_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.order_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.order_table.setAlternatingRowColors(True)
        self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.order_table.horizontalHeader().setStretchLastSection(True)
        self.order_table.setColumnWidth(0, 55)
        self.order_table.setColumnWidth(1, 85)
        self.order_table.setColumnWidth(2, 180)
        self.order_table.setColumnWidth(3, 240)
        self.order_table.setColumnWidth(4, 85)
        self.order_table.setColumnWidth(5, 80)
        self.order_table.setColumnWidth(6, 105)
        self.order_table.setColumnWidth(7, 80)
        self.order_table.setColumnWidth(8, 105)
        self.order_table.itemSelectionChanged.connect(self._on_order_selection_changed)
        self.order_table.cellDoubleClicked.connect(self._on_order_double_clicked)
        order_layout.addWidget(self.order_table, 1)

        bottom_splitter.addWidget(order_card)

        # 右侧：单笔订单详情与中奖号码高亮展示框
        detail_card = QFrame()
        detail_card.setProperty("card", True)
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(12, 10, 12, 10)
        detail_layout.setSpacing(6)

        lbl_detail = QLabel("🔍 选中订单详情 & 中奖特码高亮核对")
        lbl_detail.setProperty("sectionTitle", True)
        detail_layout.addWidget(lbl_detail)

        self.browser_order_detail = QTextBrowser()
        self.browser_order_detail.setOpenExternalLinks(False)
        detail_layout.addWidget(self.browser_order_detail, 1)

        bottom_splitter.addWidget(detail_card)
        bottom_splitter.setStretchFactor(0, 14)
        bottom_splitter.setStretchFactor(1, 6)

        v_splitter.addWidget(bottom_splitter)
        v_splitter.setStretchFactor(0, 9)
        v_splitter.setStretchFactor(1, 13)
        root_layout.addWidget(v_splitter, 1)

    def _populate_winning_combo(self) -> None:
        self.cmb_winning_num.blockSignals(True)
        self.cmb_winning_num.clear()
        self.cmb_winning_num.addItem(CartoonIconManager.get_icon("act_settle"), "00 - 未开奖 (仅统计收单)", 0)
        for num in range(1, 50):
            zod = self.controller.attr_engine.get_zodiac_of_number(num)
            wave = self.controller.attr_engine.get_wave_color(num)
            wave_cn = {"red": "红波", "blue": "蓝波", "green": "绿波"}.get(wave, "")
            self.cmb_winning_num.addItem(
                CartoonIconManager.get_icon(f"ball_{wave}"),
                f"{num:02d} 号  [{zod} · {wave_cn}]",
                num,
            )
        self.cmb_winning_num.blockSignals(False)

    def refresh_data(self) -> None:
        self._populate_winning_combo()
        reg_cfg = self.controller.get_current_region_config()
        win_num = reg_cfg.last_winning_number if reg_cfg else 0

        idx = self.cmb_winning_num.findData(win_num)
        self.cmb_winning_num.setCurrentIndex(idx if idx >= 0 else 0)

        # 刷新客户筛选下拉框
        cur_filter = self.cmb_client_filter.currentText()
        self.cmb_client_filter.blockSignals(True)
        self.cmb_client_filter.clear()
        self.cmb_client_filter.addItem("全部")
        for c in self.controller.client_repo.list_clients(self.controller.current_region):
            if c.total_bet > 0 or c.name == self.controller.get_active_client().name:
                self.cmb_client_filter.addItem(c.name)
        f_idx = self.cmb_client_filter.findText(cur_filter)
        self.cmb_client_filter.setCurrentIndex(f_idx if f_idx >= 0 else 0)
        self.cmb_client_filter.blockSignals(False)

        # 计算分人结算表
        client_items, grand_total = self.controller.settlement_service.settle_region(
            self.controller.current_region, win_num if win_num > 0 else None
        )
        self._populate_client_settlement_table(client_items, grand_total, win_num)
        self._refresh_orders_table()

    def _populate_client_settlement_table(
        self,
        items: List[ClientSettlementItem],
        grand_total: ClientSettlementItem,
        win_num: int,
    ) -> None:
        is_dark = self.controller.app_config.theme_mode == "dark"
        all_rows = items + [grand_total]
        self.client_table.setRowCount(len(all_rows))
        bold_font = QFont("Microsoft YaHei UI", 9, QFont.Bold)

        for r_idx, st in enumerate(all_rows):
            is_total_row = r_idx == len(all_rows) - 1
            vals = [
                st.client_name,
                str(st.order_count),
                "-" if is_total_row else f"{st.odds:g}",
                "-" if is_total_row else f"{st.rebate * 100:.1f}%",
                f"{st.total_bet:g}",
                f"{st.winning_bet:g}" if win_num > 0 else "-",
                f"{st.pnl_no_rebate:+.2f}" if win_num > 0 else "-",
                f"{st.rebate_amount:+.2f}" if win_num > 0 else "-",
                f"{st.net_pnl:+.2f}" if win_num > 0 else "-",
            ]
            for c_idx, text in enumerate(vals):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignCenter)
                if is_total_row:
                    cell.setFont(bold_font)
                    cell.setBackground(QColor("#1e293b" if is_dark else "#e2e8f0"))
                if win_num > 0 and c_idx == 5 and st.winning_bet > 0:
                    cell.setFont(bold_font)
                    cell.setForeground(QColor("#dc2626" if not is_dark else "#f87171"))
                elif win_num > 0 and c_idx in (6, 8):
                    val_num = st.pnl_no_rebate if c_idx == 6 else st.net_pnl
                    cell.setFont(bold_font)
                    cell.setForeground(QColor(ThemeManager.get_pnl_color_hex(val_num, is_dark)))
                self.client_table.setItem(r_idx, c_idx, cell)

        win_str = f"{win_num:02d}号" if win_num > 0 else "未开奖"
        self.lbl_grand_summary.setText(
            f"📌 开奖特码: {win_str}  |  总收单: {grand_total.total_bet:g} 元  |  "
            f"中码总额: {grand_total.winning_bet:g} 元  |  "
            f"庄家净盈亏(含回水): {grand_total.net_pnl:+.2f} 元"
        )

    def _refresh_orders_table(self) -> None:
        region = self.controller.current_region
        c_filter = self.cmb_client_filter.currentText()
        kw_filter = self.edit_search.text().strip()
        reg_cfg = self.controller.get_current_region_config()
        win_num = reg_cfg.last_winning_number if reg_cfg else 0
        is_dark = self.controller.app_config.theme_mode == "dark"

        self._current_orders = self.controller.order_repo.list_orders(
            region, client_filter=c_filter, keyword_filter=kw_filter
        )
        self.order_table.setRowCount(len(self._current_orders))
        bold_font = QFont("Microsoft YaHei UI", 9, QFont.Bold)

        for r_idx, order in enumerate(self._current_orders):
            raw_preview = order.raw_text.replace("\n", " ↵ ")
            parsed_preview = order.parsed_content.replace("\n", " | ")
            vals = [
                str(order.seq_no),
                order.client_name,
                raw_preview,
                parsed_preview,
                f"{order.total_amount:g}",
                f"{order.winning_amount:g}" if win_num > 0 else "-",
                f"{order.pnl_no_rebate:+.2f}" if win_num > 0 else "-",
                f"{order.rebate_amount:+.2f}" if win_num > 0 else "-",
                f"{order.net_pnl:+.2f}" if win_num > 0 else "-",
                order.created_at,
            ]
            for c_idx, text in enumerate(vals):
                cell = QTableWidgetItem(text)
                if c_idx == 0:
                    cell.setData(Qt.UserRole, order.id)
                if c_idx in (2, 3):
                    cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                else:
                    cell.setTextAlignment(Qt.AlignCenter)

                if win_num > 0 and c_idx == 5 and order.winning_amount > 0:
                    cell.setFont(bold_font)
                    cell.setForeground(QColor("#dc2626" if not is_dark else "#f87171"))
                elif win_num > 0 and c_idx in (6, 8):
                    v = order.pnl_no_rebate if c_idx == 6 else order.net_pnl
                    cell.setFont(bold_font)
                    cell.setForeground(QColor(ThemeManager.get_pnl_color_hex(v, is_dark)))
                self.order_table.setItem(r_idx, c_idx, cell)

        if self._current_orders:
            self.order_table.selectRow(len(self._current_orders) - 1)
        else:
            self.browser_order_detail.setHtml("<p style='color:gray;'>当前筛选条件下暂无订单记录。</p>")

    def _on_order_selection_changed(self) -> None:
        row = self.order_table.currentRow()
        if row < 0 or row >= len(self._current_orders):
            return
        order = self._current_orders[row]
        reg_cfg = self.controller.get_current_region_config()
        win_num = reg_cfg.last_winning_number if reg_cfg else 0

        highlighted_html = self.controller.settlement_service.highlight_winning_number_html(
            order.parsed_content, win_num
        )
        raw_html = order.raw_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        win_badge = (
            f"<span style='color:#dc2626;font-weight:bold;'>{win_num:02d} 号 (中码: {order.winning_amount:g} 元)</span>"
            if win_num > 0
            else "未设置开奖号码"
        )
        html = f"""
        <div style="font-family:'Microsoft YaHei UI'; font-size:13px; line-height:1.5;">
            <p><b>订单序号：</b>#{order.seq_no} &nbsp;&nbsp; <b>所属客户：</b>{order.client_name}</p>
            <p><b>录入时间：</b>{order.created_at} &nbsp;&nbsp; <b>下单总额：</b><b>{order.total_amount:g} 元</b></p>
            <p><b>开奖状态：</b>{win_badge} &nbsp;&nbsp; <b>净盈亏：</b><b>{order.net_pnl:+.2f} 元</b></p>
            <hr>
            <p><b>【微信原始消息】：</b></p>
            <div style="background:rgba(148,163,184,0.12); padding:8px; border-radius:6px;">{raw_html}</div>
            <p style="margin-top:10px;"><b>【解析后标准押注内容（中奖号码红色高亮）】：</b></p>
            <div style="background:rgba(37,99,235,0.08); padding:8px; border-radius:6px;">{highlighted_html}</div>
        </div>
        """
        self.browser_order_detail.setHtml(html)

    def _on_client_row_clicked(self, row: int, _col: int) -> None:
        item = self.client_table.item(row, 0)
        if not item:
            return
        c_name = item.text()
        if c_name == "合计：":
            self.cmb_client_filter.setCurrentIndex(0)
        else:
            idx = self.cmb_client_filter.findText(c_name)
            if idx >= 0:
                self.cmb_client_filter.setCurrentIndex(idx)

    def _on_run_settlement(self) -> None:
        win_num = int(self.cmb_winning_num.currentData() or 0)
        self.controller.settlement_service.settle_region(
            self.controller.current_region, win_num if win_num > 0 else None
        )
        self.refresh_data()
        self.data_changed.emit()

    def _on_clear_winning_number(self) -> None:
        self.cmb_winning_num.setCurrentIndex(0)
        self.controller.settlement_service.settle_region(self.controller.current_region, None)
        self.refresh_data()
        self.data_changed.emit()

    def _on_copy_settlement_bill(self) -> None:
        region = self.controller.current_region
        reg_cfg = self.controller.get_current_region_config()
        win_num = reg_cfg.last_winning_number if reg_cfg else 0
        items, grand = self.controller.settlement_service.settle_region(
            region, win_num if win_num > 0 else None
        )
        lines = [f"【{region} · 分人算账汇总单】"]
        if win_num > 0:
            zod = self.controller.attr_engine.get_zodiac_of_number(win_num)
            lines.append(f"本期开奖特码：{win_num:02d} ({zod})")
        lines.append("-" * 42)
        for st in items:
            if win_num > 0:
                lines.append(
                    f"{st.client_name}: 收单 {st.total_bet:g} | 中码 {st.winning_bet:g} | "
                    f"回水 {st.rebate_amount:+.2f} | 净盈亏 {st.net_pnl:+.2f}"
                )
            else:
                lines.append(f"{st.client_name}: 收单总额 {st.total_bet:g} ({st.order_count}笔)")
        lines.append("-" * 42)
        if win_num > 0:
            lines.append(
                f"合计：总收单 {grand.total_bet:g} | 总中码 {grand.winning_bet:g} | "
                f"总回水 {grand.rebate_amount:+.2f} | 庄家净盈亏 {grand.net_pnl:+.2f}"
            )
        else:
            lines.append(f"合计：总收单 {grand.total_bet:g} ({grand.order_count}笔)")
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "账单已复制", "分人结账汇总单已复制到剪贴板！")

    def _on_order_double_clicked(self, row: int, _col: int) -> None:
        self._delete_order_at_row(row)

    def _on_delete_selected_order(self) -> None:
        row = self.order_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的订单行！")
            return
        self._delete_order_at_row(row)

    def _delete_order_at_row(self, row: int) -> None:
        if row < 0 or row >= len(self._current_orders):
            return
        order = self._current_orders[row]
        reply = QMessageBox.question(
            self,
            "确认撤单并扣减押注",
            f"确定要删除第 #{order.seq_no} 笔订单（客户：{order.client_name}，金额：{order.total_amount:g} 元）吗？\n\n"
            f"删除后将自动从【{order.client_name}】的 1-49 号统计中扣回该笔押注金额！",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes and order.id is not None:
            self.controller.settlement_service.delete_order_and_revert_bets(order.id)
            self.refresh_data()
            self.data_changed.emit()

    def _on_rebuild_bets(self) -> None:
        self.controller.settlement_service.rebuild_region_client_bets_from_orders(
            self.controller.current_region
        )
        self.refresh_data()
        self.data_changed.emit()
        QMessageBox.information(self, "校验完成", "已根据当前盘口所有订单明细重新校准 1-49 号分人统计金额！")

    def _on_clear_region_all(self) -> None:
        region = self.controller.current_region
        reply = QMessageBox.warning(
            self,
            "危险操作确认",
            f"确定要清空【{region}】盘口下的所有订单明细、分人统计押注与吃码上报记录吗？\n（客户名单与赔率配置会保留）\n\n"
            f"💡 清空前系统会自动将本盘账目归档到「历史日期回看」，可随时查看或恢复。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.clear_region_with_auto_archive(region)
            self.refresh_data()
            self.data_changed.emit()

    def clear_region_with_auto_archive(self, region: str):
        """清空盘口前自动归档当前账目，保证任何一天的历史都不会丢失；返回归档记录（无订单时为 None）"""
        record = self.controller.history_service.archive_current_region_session(
            region, custom_title="清空本盘前自动归档"
        )
        self.controller.settlement_service.clear_region_all_data(region)
        return record
