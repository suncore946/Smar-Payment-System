"""
主控看板与实时风控页面 (DashboardTab)
展示：
1. 核心指标卡片（全盘总收单、当前客户押注、最大风险预警、盈亏分布）
2. 全盘 12生肖×49号码 实时汇总矩阵（带红蓝绿波色标识与生肖小计）
3. 当前客户（分人统计）12生肖×49号码 个人押注矩阵及独立赔率/回水设置
4. 1-49号 总额大小排序与实时风险监控榜（支持按金额降序或按号码顺序切换）
"""

from __future__ import annotations
from typing import Callable, Dict, Optional
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from src.services.app_controller import ApplicationController
from .icon_manager import CartoonIconManager
from .styles import ThemeManager


class DashboardTab(QWidget):
    """主控看板与实时风控视图组件"""

    def __init__(
        self,
        controller: ApplicationController,
        on_data_changed: Callable[[], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.on_data_changed = on_data_changed
        self._sort_by_amount = True
        self._updating_ui = False
        self._init_ui()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 6, 8, 6)
        root_layout.setSpacing(6)

        # 1. 顶部 KPI 指标与快捷风控参数栏
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.card_total_pool, self.lbl_total_pool = self._create_kpi_card("全盘总金额", "¥ 0", "KpiCard", "kpi_pool")
        self.card_client_pool, self.lbl_client_pool = self._create_kpi_card("当前客户总额", "¥ 0", "KpiCard", "kpi_client")
        self.card_max_risk, self.lbl_max_risk = self._create_kpi_card("头号风险 / 最大亏损", "--", "KpiCardDanger", "kpi_risk")
        self.card_profit_loss, self.lbl_profit_loss = self._create_kpi_card("盈余号数 / 亏损号数", "0 / 0", "KpiCardSuccess", "kpi_profit")

        top_bar.addWidget(self.card_total_pool, 1)
        top_bar.addWidget(self.card_client_pool, 1)
        top_bar.addWidget(self.card_max_risk, 1)
        top_bar.addWidget(self.card_profit_loss, 1)

        # 盘口全局赔率/回水与客户赔率/回水设置框
        param_frame = QFrame()
        param_frame.setObjectName("CardFrame")
        param_layout = QGridLayout(param_frame)
        param_layout.setContentsMargins(8, 4, 8, 4)
        param_layout.setHorizontalSpacing(6)
        param_layout.setVerticalSpacing(2)

        param_layout.addWidget(QLabel("全盘风险赔率:"), 0, 0)
        self.spin_global_odds = QDoubleSpinBox()
        self.spin_global_odds.setRange(1.0, 999.0)
        self.spin_global_odds.setDecimals(2)
        self.spin_global_odds.setSingleStep(1.0)
        self.spin_global_odds.valueChanged.connect(self._on_global_odds_rebate_changed)
        param_layout.addWidget(self.spin_global_odds, 0, 1)

        param_layout.addWidget(QLabel("全盘回水:"), 0, 2)
        self.spin_global_rebate = QDoubleSpinBox()
        self.spin_global_rebate.setRange(0.0, 1.0)
        self.spin_global_rebate.setDecimals(4)
        self.spin_global_rebate.setSingleStep(0.005)
        self.spin_global_rebate.valueChanged.connect(self._on_global_odds_rebate_changed)
        param_layout.addWidget(self.spin_global_rebate, 0, 3)

        self.btn_unify_odds = QPushButton("统一所有客户赔率回水")
        self.btn_unify_odds.setObjectName("SecondaryBtn")
        self.btn_unify_odds.clicked.connect(self._on_unify_all_clients_odds)
        param_layout.addWidget(self.btn_unify_odds, 0, 4)

        param_layout.addWidget(QLabel("当前客户赔率:"), 1, 0)
        self.spin_client_odds = QDoubleSpinBox()
        self.spin_client_odds.setRange(1.0, 999.0)
        self.spin_client_odds.setDecimals(2)
        self.spin_client_odds.setSingleStep(1.0)
        self.spin_client_odds.valueChanged.connect(self._on_client_odds_rebate_changed)
        param_layout.addWidget(self.spin_client_odds, 1, 1)

        param_layout.addWidget(QLabel("客户回水:"), 1, 2)
        self.spin_client_rebate = QDoubleSpinBox()
        self.spin_client_rebate.setRange(0.0, 1.0)
        self.spin_client_rebate.setDecimals(4)
        self.spin_client_rebate.setSingleStep(0.005)
        self.spin_client_rebate.valueChanged.connect(self._on_client_odds_rebate_changed)
        param_layout.addWidget(self.spin_client_rebate, 1, 3)

        self.btn_clear_region = QPushButton("🗑️ 清空当前盘口数据")
        self.btn_clear_region.setObjectName("DangerBtn")
        self.btn_clear_region.clicked.connect(self._on_clear_region_clicked)
        param_layout.addWidget(self.btn_clear_region, 1, 4)

        top_bar.addWidget(param_frame, 2)
        root_layout.addLayout(top_bar)

        # 2. 主分割区：左侧（全盘12生肖矩阵 + 当前客户12生肖矩阵），右侧（总额大小排序与风险监控榜）
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧上下两个矩阵
        left_splitter = QSplitter(Qt.Vertical)

        self.grp_region_matrix = QGroupBox("🌟 全盘 12生肖 × 49号码 实时汇总矩阵")
        reg_m_layout = QVBoxLayout(self.grp_region_matrix)
        reg_m_layout.setContentsMargins(6, 8, 6, 6)
        self.tbl_region_matrix = self._create_zodiac_matrix_table()
        reg_m_layout.addWidget(self.tbl_region_matrix)
        left_splitter.addWidget(self.grp_region_matrix)

        self.grp_client_matrix = QGroupBox("👤 当前客户（分人统计）12生肖 × 49号码 押注矩阵")
        cli_m_layout = QVBoxLayout(self.grp_client_matrix)
        cli_m_layout.setContentsMargins(6, 8, 6, 6)
        self.tbl_client_matrix = self._create_zodiac_matrix_table()
        cli_m_layout.addWidget(self.tbl_client_matrix)
        left_splitter.addWidget(self.grp_client_matrix)

        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 1)
        main_splitter.addWidget(left_splitter)

        # 右侧：1-49号 总额大小排序与风险值排行榜
        right_group = QGroupBox("📈 1-49号 总额大小排序与实时风险监控榜")
        right_layout = QVBoxLayout(right_group)
        right_layout.setContentsMargins(6, 8, 6, 6)

        sort_bar = QHBoxLayout()
        self.lbl_ranking_mode = QLabel("当前排序：按押注金额从高到低（风险预警模式）")
        self.lbl_ranking_mode.setStyleSheet("font-weight: bold; color: #1D4ED8;")
        sort_bar.addWidget(self.lbl_ranking_mode)
        sort_bar.addStretch()

        self.btn_toggle_sort = QPushButton("🔄 切换为：按号码(01-49)顺序")
        self.btn_toggle_sort.setObjectName("SecondaryBtn")
        self.btn_toggle_sort.clicked.connect(self._on_toggle_sort_clicked)
        sort_bar.addWidget(self.btn_toggle_sort)
        right_layout.addLayout(sort_bar)

        self.tbl_risk_ranking = QTableWidget(49, 6)
        self.tbl_risk_ranking.setHorizontalHeaderLabels(
            ["排名", "生肖", "号码", "汇总金额", "风险值 (预计盈亏)", "风控状态"]
        )
        self.tbl_risk_ranking.verticalHeader().setVisible(False)
        self.tbl_risk_ranking.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_risk_ranking.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_risk_ranking.setAlternatingRowColors(True)
        hdr = self.tbl_risk_ranking.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        right_layout.addWidget(self.tbl_risk_ranking)

        main_splitter.addWidget(right_group)
        # 调整水平比例：大幅拓宽左侧两个矩阵宽度，右侧保留合理比例
        main_splitter.setStretchFactor(0, 15)
        main_splitter.setStretchFactor(1, 7)
        main_splitter.setSizes([920, 480])

        root_layout.addWidget(main_splitter, 1)

    @staticmethod
    def _create_kpi_card(title: str, init_val: str, obj_name: str, icon_name: str = "kpi_pool") -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName(obj_name)
        outer = QHBoxLayout(card)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(8)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(CartoonIconManager.render_pixmap(icon_name, 36))
        outer.addWidget(lbl_icon)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; color: #64748B; font-weight: bold;")
        lbl_v = QLabel(init_val)
        lbl_v.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(lbl_t)
        layout.addWidget(lbl_v)
        outer.addLayout(layout, 1)
        return card, lbl_v

    @staticmethod
    def _create_zodiac_matrix_table() -> QTableWidget:
        tbl = QTableWidget(12, 12)
        tbl.setHorizontalHeaderLabels(
            ["生肖", "号码", "金额", "号码", "金额", "号码", "金额", "号码", "金额", "号码", "金额", "本肖合计"]
        )
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.setAlternatingRowColors(True)

        # 隐藏水平与垂直滚动条，确保所有生肖与全部号码完全露出一览无余
        tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        hdr = tbl.horizontalHeader()
        hdr.setHighlightSections(False)
        hdr.setDefaultSectionSize(55)

        # 优化各列伸缩策略：生肖与号码列紧凑，金额列与合计列自适应宽度
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 生肖列
        for c_pair in range(5):
            col_num = 1 + c_pair * 2
            col_amt = col_num + 1
            hdr.setSectionResizeMode(col_num, QHeaderView.ResizeToContents)  # 号码列紧凑
            hdr.setSectionResizeMode(col_amt, QHeaderView.Stretch)           # 金额列伸展填充
        hdr.setSectionResizeMode(11, QHeaderView.Stretch)                   # 本肖合计列

        # 紧凑内边距样式，确保 12 行无需滚动条即可完整展示
        tbl.setStyleSheet("""
            QTableWidget {
                padding: 0px;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 1px 2px;
            }
            QHeaderView::section {
                padding: 2px 2px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        return tbl

    def _on_toggle_sort_clicked(self) -> None:
        self._sort_by_amount = not self._sort_by_amount
        if self._sort_by_amount:
            self.lbl_ranking_mode.setText("当前排序：按押注金额从高到低（风险预警模式）")
            self.btn_toggle_sort.setText("切换为：按号码(01-49)顺序")
        else:
            self.lbl_ranking_mode.setText("当前排序：按号码 01 ~ 49 自然顺序")
            self.btn_toggle_sort.setText("切换为：按总额大小降序")
        self.refresh_data()

    def _on_global_odds_rebate_changed(self) -> None:
        if self._updating_ui:
            return
        reg = self.controller.get_current_region_config()
        reg.global_odds = round(self.spin_global_odds.value(), 2)
        reg.global_rebate = round(self.spin_global_rebate.value(), 4)
        self.controller.region_repo.save_region(reg)
        self.refresh_data()

    def _on_client_odds_rebate_changed(self) -> None:
        if self._updating_ui:
            return
        client = self.controller.get_active_client()
        client.odds = round(self.spin_client_odds.value(), 2)
        client.rebate = round(self.spin_client_rebate.value(), 4)
        self.controller.client_repo.save_client(client)

    def _on_unify_all_clients_odds(self) -> None:
        reg = self.controller.get_current_region_config()
        reply = QMessageBox.question(
            self,
            "统一下单人赔率回水",
            f"确定将【{reg.name}】所有客户的赔率统一设为 {reg.global_odds:g}、回水统一设为 {reg.global_rebate:g} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.controller.client_repo.unify_odds_and_rebate(reg.name, reg.global_odds, reg.global_rebate)
            self.refresh_data()
            self.on_data_changed()

    def _on_clear_region_clicked(self) -> None:
        reg_name = self.controller.current_region
        reply = QMessageBox.warning(
            self,
            "确认清空盘口数据",
            f"确定要清空【{reg_name}】的所有订单明细、分人统计金额与吃码上报状态吗？\n（清空前建议先备份或导出Excel）",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.controller.settlement_service.clear_region_all_data(reg_name)
            self.on_data_changed()

    def refresh_data(self) -> None:
        self._updating_ui = True
        try:
            dark_mode = self.controller.app_config.theme_mode == "dark"
            reg = self.controller.get_current_region_config()
            active_client = self.controller.get_active_client(reg.name)

            self.spin_global_odds.setValue(reg.global_odds)
            self.spin_global_rebate.setValue(reg.global_rebate)
            self.spin_client_odds.setValue(active_client.odds)
            self.spin_client_rebate.setValue(active_client.rebate)

            self.grp_region_matrix.setTitle(
                f"🌟 【{reg.name}】全盘 12生肖 × 49号码 实时汇总矩阵（本命年：{self.controller.attr_engine.base_zodiac}年）"
            )
            self.grp_client_matrix.setTitle(
                f"👤 当前客户：【{active_client.name}】分人统计矩阵（赔率:{active_client.odds:g} | 回水:{active_client.rebate:g}）"
            )

            risk_items = self.controller.risk_service.get_region_risk_items(reg.name)
            num_to_risk = {it.number: it for it in risk_items}
            total_pool = round(sum(it.total_bet for it in risk_items), 2)
            client_pool = active_client.total_bet

            # 填充两个 12生肖×49号 矩阵
            zodiac_rows = self.controller.attr_engine.get_display_zodiac_rows()
            self._populate_matrix_table(
                self.tbl_region_matrix,
                zodiac_rows,
                {n: num_to_risk[n].total_bet for n in range(1, 50)},
                dark_mode,
            )
            self._populate_matrix_table(
                self.tbl_client_matrix,
                zodiac_rows,
                active_client.number_bets,
                dark_mode,
            )

            # 排序与填充右侧风险榜
            sorted_by_risk = self.controller.risk_service.get_sorted_risk_ranking(reg.name)
            display_list = sorted_by_risk if self._sort_by_amount else risk_items

            profit_count = sum(1 for it in risk_items if it.full_risk_value >= 0)
            loss_count = 49 - profit_count

            top_risk_item = sorted_by_risk[0] if sorted_by_risk else None
            self.lbl_total_pool.setText(f"¥ {total_pool:,.2f}".rstrip("0").rstrip("."))
            self.lbl_client_pool.setText(f"{active_client.name}: ¥ {client_pool:,.2f}".rstrip("0").rstrip("."))
            if top_risk_item and top_risk_item.total_bet > 0:
                self.lbl_max_risk.setText(
                    f"{top_risk_item.number_str}号({top_risk_item.zodiac}) | {top_risk_item.full_risk_value:+.1f}"
                )
            else:
                self.lbl_max_risk.setText("暂无风险 (¥ 0)")
            self.lbl_profit_loss.setText(f"盈 {profit_count} 号 / 亏 {loss_count} 号")

            bold_font = QFont("Microsoft YaHei UI", 10, QFont.Bold)
            for row_idx, it in enumerate(display_list):
                self.tbl_risk_ranking.setRowHeight(row_idx, 26)
                rank_item = QTableWidgetItem(str(row_idx + 1))
                rank_item.setTextAlignment(Qt.AlignCenter)

                z_item = QTableWidgetItem(it.zodiac)
                z_item.setIcon(CartoonIconManager.get_icon(f"zodiac_{it.zodiac}"))
                z_item.setTextAlignment(Qt.AlignCenter)
                z_item.setFont(bold_font)

                num_item = QTableWidgetItem(it.number_str)
                num_item.setIcon(CartoonIconManager.get_icon(f"ball_{it.wave_color}"))
                num_item.setTextAlignment(Qt.AlignCenter)
                num_item.setFont(bold_font)
                bg, fg = ThemeManager.get_wave_bg_fg(it.wave_color, dark_mode)
                num_item.setBackground(QBrush(bg))
                num_item.setForeground(QBrush(fg))

                bet_item = QTableWidgetItem(f"{it.total_bet:g}")
                bet_item.setTextAlignment(Qt.AlignCenter)
                if it.total_bet > 0:
                    bet_item.setFont(bold_font)

                risk_item = QTableWidgetItem(f"{it.full_risk_value:+.2f}".rstrip("0").rstrip("."))
                risk_item.setTextAlignment(Qt.AlignCenter)
                risk_item.setFont(bold_font)
                risk_item.setForeground(QBrush(ThemeManager.get_pnl_color(it.full_risk_value, dark_mode)))

                status_str = "亏损预警" if it.full_risk_value < 0 else "安全盈余"
                status_item = QTableWidgetItem(status_str)
                status_item.setIcon(
                    CartoonIconManager.get_icon("kpi_risk" if it.full_risk_value < 0 else "act_add_order")
                )
                status_item.setTextAlignment(Qt.AlignCenter)
                status_item.setForeground(QBrush(ThemeManager.get_pnl_color(it.full_risk_value, dark_mode)))

                self.tbl_risk_ranking.setItem(row_idx, 0, rank_item)
                self.tbl_risk_ranking.setItem(row_idx, 1, z_item)
                self.tbl_risk_ranking.setItem(row_idx, 2, num_item)
                self.tbl_risk_ranking.setItem(row_idx, 3, bet_item)
                self.tbl_risk_ranking.setItem(row_idx, 4, risk_item)
                self.tbl_risk_ranking.setItem(row_idx, 5, status_item)
        finally:
            self._updating_ui = False

    def _populate_matrix_table(
        self,
        table: QTableWidget,
        zodiac_rows: list[tuple[str, list[int]]],
        bets_map: Dict[int, float],
        dark_mode: bool,
    ) -> None:
        bold_font = QFont("Microsoft YaHei UI", 9, QFont.Bold)
        for r_idx, (zodiac, nums) in enumerate(zodiac_rows):
            table.setRowHeight(r_idx, 22)
            z_item = QTableWidgetItem(zodiac)
            z_item.setIcon(CartoonIconManager.get_icon(f"zodiac_{zodiac}"))
            z_item.setTextAlignment(Qt.AlignCenter)
            z_item.setFont(bold_font)
            table.setItem(r_idx, 0, z_item)

            row_sum = 0.0
            for c_pair in range(5):
                col_num = 1 + c_pair * 2
                col_amt = col_num + 1
                if c_pair < len(nums):
                    n = nums[c_pair]
                    amt = round(bets_map.get(n, 0.0), 2)
                    row_sum = round(row_sum + amt, 2)

                    n_item = QTableWidgetItem(f"{n:02d}")
                    n_item.setTextAlignment(Qt.AlignCenter)
                    n_item.setFont(bold_font)
                    wave = self.controller.attr_engine.get_wave_color(n)
                    bg, fg = ThemeManager.get_wave_bg_fg(wave, dark_mode)
                    n_item.setBackground(QBrush(bg))
                    n_item.setForeground(QBrush(fg))

                    a_item = QTableWidgetItem(f"{amt:g}" if amt != 0 else "0")
                    a_item.setTextAlignment(Qt.AlignCenter)
                    if amt > 0:
                        a_item.setFont(bold_font)
                        a_item.setForeground(QBrush(ThemeManager.get_pnl_color(-1, dark_mode)))
                    table.setItem(r_idx, col_num, n_item)
                    table.setItem(r_idx, col_amt, a_item)
                else:
                    table.setItem(r_idx, col_num, QTableWidgetItem(""))
                    table.setItem(r_idx, col_amt, QTableWidgetItem(""))

            sum_item = QTableWidgetItem(f"{row_sum:g}")
            sum_item.setTextAlignment(Qt.AlignCenter)
            sum_item.setFont(bold_font)
            table.setItem(r_idx, 11, sum_item)
