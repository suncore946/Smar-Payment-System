"""
Tab 6: 使用说明与快捷键指南中心 (HelpGuideTab)
提供图文并茂、可搜索、可交互试玩的系统使用手册：
1. 新手 5 步极速上手指南（支持一键跳转对应工作台）
2. 微信/QQ智能收单口语语法大全（14 大类真实报单格式 + 一键填入收单台互动试玩）
3. 吃码风控、二分法最大亏损反推与开奖算账核心公式详解
4. 全局与工作台快捷键实时速查表（与设置页自定义快捷键实时同步，支持一键前往修改）
5. 常见问题解答 (FAQ) 与跨电脑数据迁移指南
"""

from __future__ import annotations
from typing import List, Tuple
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from src.domain.models import SHORTCUT_DEFINITIONS
from src.services.app_controller import ApplicationController
from src.ui.icon_manager import CartoonIconManager


class HelpGuideTab(QWidget):
    """系统使用说明、微信报单语法大全与快捷键指南标签页"""

    # 信号：请求跳转到主窗口指定索引的 Tab
    navigate_tab_requested = pyqtSignal(int)
    # 信号：请求跳转到设置页的「快捷键设置」子页
    open_shortcut_settings_requested = pyqtSignal()
    # 信号：请求将示例报单文本一键填入「微信智能收单台」并执行识别
    try_wechat_sample_requested = pyqtSignal(str)

    SYNTAX_EXAMPLES: List[Tuple[str, str, str, str]] = [
        ("1. 号码直投 (各买)", "01.12.24.49各50  或  3,15,27各100", "每个指定号码各买对应金额", "01,12,24,49 各 50 元（共 200 元）"),
        ("2. 十二生肖报单", "牛虎兔各码25  或  马羊各100", "按当前本命年将生肖自动展开为对应号码", "牛/虎/兔所含全部号码每号各 25 元"),
        ("3. 生肖整肖平摊", "羊狗各五百  (在各肖模式下) 或 龙共400", "将金额平摊到该生肖包含的 4 个（或 5 个）号码上", "龙肖 4 个号平摊 400 元，每号 100 元"),
        ("4. 主肖(本命) / 平肖", "主肖各50  或  平肖各20", "本命年当年生肖包含 5 个号（含 49 号），其余 11 肖各 4 个号", "马年下：马肖 01,13,25,37,49 共 5 个号"),
        ("5. 红波 / 蓝波 / 绿波", "红波各20  或  蓝波共320", "自动匹配红波(17码)、蓝波(16码)、绿波(16码)", "红波全部号码每号 20 元"),
        ("6. 半波 / 波色单双大小", "红单各30、蓝双各50、绿大各40", "自动取波色与单双/大小的交集号码", "红波且为单数的号码每号 30 元"),
        ("7. 单双 / 大小 / 合数", "单各20、大共500、合单各15", "01-24 为小，25-49 为大；十位+个位奇偶为合单/合双", "大码(25-49 共 25 个号)平摊 500 元，每号 20 元"),
        ("8. 头数 / 尾数组合", "014头各50  或  3头4头每个数10  或  268尾各30", "0头(01-09)、1头(10-19)...；尾数按个位数字匹配", "0头、1头、4头所有号码每号 50 元"),
        ("9. 区间连号范围", "1到25各30  或  10至20各50", "自动展开起止范围内的全部连续号码", "01~25 号共 25 个号码每号 30 元"),
        ("10. 小数点金额格式", "23.166元  40.165元", "开启小数点识别时，点号前为特码号码，点号后为金额", "23 号买 166 元，40 号买 165 元"),
        ("11. 中文口语大写金额", "羊狗各五  或  08.18各一千元  或  鼠牛各二百五", "自动将「十/百/千/块/米/元」中文数字转为阿拉伯数字", "羊狗每号 5 元；08,18 每号 1000 元"),
        ("12. 反码 / 杀码 / 不中", "反码牛虎各20  或  杀红波各50", "自动取所选号码在 01-49 中的补集（即排除这些号后的其余号码）", "除牛虎外的其余 10 个生肖号码每号 20 元"),
        ("13. 岁数自动换算号码", "25岁各30  或  18岁26岁各50", "根据设置页「岁数模式」按号码或对应生肖换算", "自动映射对应岁数号码每号 30 元"),
        ("14. 负数退单 / 冲正减单", "08.18各-50  (或点击「转为负数」按钮)", "金额为负数时自动从当前客户与全盘汇总中扣减对应押注", "冲减 08、18 号各 50 元押注"),
    ]

    INTERACTIVE_SAMPLES: List[Tuple[str, str, str]] = [
        (
            "📦 实战案例 1：生肖 + 散号 + 头尾混合报单",
            "涵盖多生肖各码、圆点分隔散号、多头数与总额平摊的典型微信群报单",
            "牛虎兔各码25\n羊各码80\n01.12.24.11.07.03各50\n3头4头每个数10\n大共500元",
        ),
        (
            "📦 实战案例 2：口语中文数字 + 小数点快报单",
            "测试「羊狗各五」、「四百二」等中文口语金额与「号码.金额」小数点快报格式",
            "羊狗各五\n龙蛇各码一百五\n23.166元 40.165元\n014头各二十五",
        ),
        (
            "📦 实战案例 3：波色半波 + 区间连号 + 五行属性单",
            "测试红单/蓝双/绿大、区间「1到15」以及金木水火土五行组合",
            "红单各30\n蓝双各40\n1到15各20\n金行木行各50",
        ),
        (
            "📦 实战案例 4：反码包牌（杀肖/不中）高级报单",
            "客户想买「除了鼠牛之外的所有号码」或使用反码策略",
            "反码鼠牛各20\n28.38.48各100",
        ),
    ]

    def __init__(self, controller: ApplicationController, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 顶部横幅与快捷操作栏
        banner = QFrame()
        banner.setProperty("card", True)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        banner_layout.setSpacing(12)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(CartoonIconManager.render_pixmap("tab_help", 42))
        banner_layout.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        lbl_main = QLabel("📖 特码智能收单与吃码风控系统 Pro — 官方使用说明与快捷键指南")
        lbl_main.setProperty("sectionTitle", True)
        lbl_sub = QLabel(
            "零门槛 3 分钟上手 · 支持 1,955+ 微信口语词条自动解析 · 全流程本地 SQLite 实时防丢落盘 · 全键盘快捷键极速操作"
        )
        lbl_sub.setProperty("mutedText", True)
        title_box.addWidget(lbl_main)
        title_box.addWidget(lbl_sub)
        banner_layout.addLayout(title_box, 1)

        btn_go_wechat = QPushButton("💬 前往微信智能收单 (Alt+2)")
        btn_go_wechat.setIcon(CartoonIconManager.get_icon("tab_wechat"))
        btn_go_wechat.setProperty("primary", True)
        btn_go_wechat.clicked.connect(lambda: self.navigate_tab_requested.emit(1))
        banner_layout.addWidget(btn_go_wechat)

        btn_go_shortcuts = QPushButton("⌨️ 自定义快捷键设置")
        btn_go_shortcuts.setIcon(CartoonIconManager.get_icon("act_keyboard"))
        btn_go_shortcuts.clicked.connect(self.open_shortcut_settings_requested.emit)
        banner_layout.addWidget(btn_go_shortcuts)

        root_layout.addWidget(banner)

        # 5 大指南子标签页
        self.guide_tabs = QTabWidget()
        self.guide_tabs.addTab(
            self._build_quickstart_page(),
            CartoonIconManager.get_icon("tab_dashboard"),
            "🚀 1. 新手 5 步快速上手",
        )
        self.guide_tabs.addTab(
            self._build_wechat_syntax_page(),
            CartoonIconManager.get_icon("tab_wechat"),
            "💬 2. 微信收单语法大全与互动试玩",
        )
        self.guide_tabs.addTab(
            self._build_shortcuts_reference_page(),
            CartoonIconManager.get_icon("act_keyboard"),
            "⌨️ 3. 快捷键速查表 (支持自定义)",
        )
        self.guide_tabs.addTab(
            self._build_formula_and_risk_page(),
            CartoonIconManager.get_icon("tab_eat_risk"),
            "🛡️ 4. 吃码风控与算账公式详解",
        )
        self.guide_tabs.addTab(
            self._build_faq_and_safety_page(),
            CartoonIconManager.get_icon("act_db_backup"),
            "❓ 5. 常见问题与新机迁移 (FAQ)",
        )

        root_layout.addWidget(self.guide_tabs, 1)

    # =========================================================================
    # 子页 1：新手 5 步快速上手
    # =========================================================================
    def _build_quickstart_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        steps = [
            (
                "第 1 步：选择当前盘口与收单客户",
                "kpi_client",
                "• 在软件最上方导航栏选择<b>【当前盘口】</b>（默认内置：新澳门、香港、旧澳门，也可点击「新增盘口」自由扩展）。<br>"
                "• 在<b>【当前收单客户】</b>下拉框选择正在报单的客户，按快捷键 <b>Ctrl+N</b> 快速新建客户，或按 <b>F4</b> / 点击「修正客户名」快速更正当前客户姓名（系统自动级联同步更新该客户名下的所有历史订单与账目）。<br>"
                "• 如需为不同客户设置专属特码赔率（如 47 倍、48 倍）或回水比例（如 2%、5%），可在「系统设置 ➔ 客户档案与独立赔率」中随时调整。",
                "⚙️ 前往客户与赔率配置",
                5,
            ),
            (
                "第 2 步：微信/QQ复制报单智能识别 & 极速盲打入库",
                "tab_wechat",
                "• <b>方式 A（微信聊天记录粘贴识别）</b>：将客户发来的多行微信报单粘贴到左侧输入框，按 <b>Ctrl+Enter</b> 立即识别（或在设置中开启「自动监听剪贴板」，微信里一按 Ctrl+C 软件即自动解析）。确认下方预览表无误后，按 <b>F2</b> 一键入库！<br>"
                "• <b>方式 B（键盘极速盲打）</b>：按 <b>F3</b> 将光标定位于右侧极速录入框，输入号码/生肖回车、输入金额再回车，1 秒完成一单。<br>"
                "• <b>方式 C（可视化选号助手）</b>：点选 12 生肖、红蓝绿波、单双大小、头尾数（支持交集/并集与一键反码），输入金额直接添加。",
                "💬 前往微信智能收单台",
                1,
            ),
            (
                "第 3 步：主控看板实时监控 1–49 号码汇总与高危风险",
                "tab_dashboard",
                "• 每录入一笔订单，<b>【主控看板】</b>会自动按总押注金额或风险值从高到低排列 1–49 号。<br>"
                "• <b>风险值公式</b>：<code>单号风险值 = 该号总押注 × 赔率 - 全盘总收单 × (1 - 回水比例)</code>。<br>"
                "• 红色正数代表「一旦开出此特码庄家将面临的净亏损额」，绿色负数代表「开出此特码庄家净赚金额」，让您一眼锁定高危特码。",
                "📊 前往主控风控看板",
                0,
            ),
            (
                "第 4 步：吃码风控、最大亏损反推与多上庄飞单上报",
                "tab_eat_risk",
                "• <b>正向按金额吃码</b>：拖动滑块或输入单号最高吃码限额（例如每号最多自己留 200 元），超出部分自动转入「预备上报」。<br>"
                "• <b>反向按最大允许亏损自动反推（核心神器）</b>：只需输入「本期我最多能承受亏损多少元（如 5000 元）」，系统会通过二分算法在毫秒内自动反推出最佳单号吃码上限！<br>"
                "• <b>一键复制散码与多上庄归档</b>：按 <b>Ctrl+Shift+C</b> 复制预备上报散码发给上家，并点击「确认上报并归档到上庄」记录飞单流水，支持随时撤回。",
                "🛡️ 前往吃码上报风控中心",
                2,
            ),
            (
                "第 5 步：开奖特码一键对奖、分人回水核算与发群结账单",
                "tab_settlement",
                "• 开奖后切换到<b>【开奖对奖算账】</b>页（快捷键 <b>Alt+4</b>），选择本期开奖特码（01–49）并按 <b>F8</b> 立即对奖。<br>"
                "• 系统自动核算每位客户的<b>下单总额、中码奖金、回水金额与最终净盈亏</b>，并在下方订单明细中将中奖号码标红高亮。<br>"
                "• 按 <b>Ctrl+Shift+B</b> 一键复制排版整齐的「分人算账汇总单」直接粘贴到微信对账，或按 <b>Ctrl+E</b> 导出完整 Excel 财务报表！",
                "🏆 前往开奖对奖算账中心",
                3,
            ),
            (
                "第 6 步：按日期历史回看、模拟特码复盘与期数归档",
                "tab_history",
                "• 切换到<b>【历史日期回看】</b>页（快捷键 <b>Alt+6</b>），点击「今天 / 昨天 / 近7天 / 近30天 / 本月」或自选起止日期，即可回看任意一天或任意区间的全部订单与盈亏。<br>"
                "• 选择<b>「模拟特码」</b>可对历史区间内全部订单按任意 01–49 号重新对奖，只做推演、不改动原始账目。<br>"
                "• 每次「清空本盘」前系统都会<b>自动归档</b>当天账目，清空后依然可以按日期回看，也可一键恢复到当前盘口，或导出历史 Excel 报表。",
                "📅 前往历史日期回看",
                4,
            ),
        ]

        for title, icon_name, desc_html, btn_text, target_tab_idx in steps:
            card = QFrame()
            card.setProperty("card", True)
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(16, 14, 16, 14)
            c_layout.setSpacing(14)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(CartoonIconManager.render_pixmap(icon_name, 52))
            icon_lbl.setFixedSize(56, 56)
            c_layout.addWidget(icon_lbl)

            text_col = QVBoxLayout()
            t_lbl = QLabel(title)
            t_lbl.setProperty("sectionTitle", True)
            b_lbl = QLabel(desc_html)
            b_lbl.setWordWrap(True)
            b_lbl.setStyleSheet("font-size: 13px; line-height: 1.55;")
            text_col.addWidget(t_lbl)
            text_col.addWidget(b_lbl)
            c_layout.addLayout(text_col, 1)

            jump_btn = QPushButton(btn_text)
            jump_btn.setMinimumWidth(175)
            jump_btn.setMinimumHeight(36)
            jump_btn.clicked.connect(lambda _checked=False, idx=target_tab_idx: self.navigate_tab_requested.emit(idx))
            c_layout.addWidget(jump_btn)

            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # 子页 2：微信收单语法大全与互动试玩
    # =========================================================================
    def _build_wechat_syntax_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 顶部：4 个互动试玩卡片
        sample_card = QFrame()
        sample_card.setProperty("card", True)
        sc_layout = QVBoxLayout(sample_card)
        sc_layout.setContentsMargins(14, 10, 14, 10)
        sc_layout.setSpacing(8)

        lbl_try = QLabel("⚡ 互动实战演练：点击下方任意案例，即可自动填入「微信智能收单台」亲手体验识别效果！")
        lbl_try.setProperty("sectionTitle", True)
        sc_layout.addWidget(lbl_try)

        grid = QGridLayout()
        grid.setSpacing(10)
        for idx, (s_title, s_desc, s_text) in enumerate(self.INTERACTIVE_SAMPLES):
            box = QFrame()
            box.setStyleSheet(
                "QFrame { background-color: rgba(37, 99, 235, 0.06); border: 1px solid #BFDBFE; border-radius: 8px; }"
            )
            b_lay = QHBoxLayout(box)
            b_lay.setContentsMargins(12, 8, 12, 8)
            info_col = QVBoxLayout()
            l1 = QLabel(f"<b>{s_title}</b>")
            l2 = QLabel(s_desc)
            l2.setProperty("mutedText", True)
            l2.setWordWrap(True)
            info_col.addWidget(l1)
            info_col.addWidget(l2)
            b_lay.addLayout(info_col, 1)

            btn_try = QPushButton("⚡ 一键填入试玩")
            btn_try.setProperty("primary", True)
            btn_try.clicked.connect(lambda _checked=False, txt=s_text: self.try_wechat_sample_requested.emit(txt))
            b_lay.addWidget(btn_try)
            grid.addWidget(box, idx // 2, idx % 2)

        sc_layout.addLayout(grid)
        layout.addWidget(sample_card)

        # 下方：14 类语法对照表（支持搜索过滤）
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("🔍 搜索报单语法或口语示例:"))
        self.edit_syntax_search = QLineEdit()
        self.edit_syntax_search.setPlaceholderText("输入关键词过滤（如：生肖、波色、小数点、反码、头尾、退单）...")
        self.edit_syntax_search.textChanged.connect(self._filter_syntax_table)
        search_bar.addWidget(self.edit_syntax_search, 1)
        layout.addLayout(search_bar)

        self.syntax_table = QTableWidget(0, 4)
        self.syntax_table.setHorizontalHeaderLabels(
            ["语法分类", "微信/QQ 报单写法示例", "智能解析规则说明", "解析结果示例"]
        )
        self.syntax_table.verticalHeader().setVisible(False)
        self.syntax_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.syntax_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.syntax_table.setAlternatingRowColors(True)
        self.syntax_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.syntax_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.syntax_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.syntax_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.syntax_table, 1)

        self._filter_syntax_table()
        return page

    def _filter_syntax_table(self) -> None:
        kw = self.edit_syntax_search.text().strip().lower()
        rows = [
            r for r in self.SYNTAX_EXAMPLES
            if not kw or any(kw in col.lower() for col in r)
        ]
        self.syntax_table.setRowCount(len(rows))
        bold_font = QFont("Microsoft YaHei UI", 9, QFont.Bold)
        for r_idx, (cat, ex, rule, res) in enumerate(rows):
            self.syntax_table.setRowHeight(r_idx, 32)
            i0 = QTableWidgetItem(cat)
            i0.setFont(bold_font)
            i1 = QTableWidgetItem(ex)
            i1.setForeground(QColor("#1D4ED8"))
            i2 = QTableWidgetItem(rule)
            i3 = QTableWidgetItem(res)
            i3.setForeground(QColor("#15803D"))
            for c_idx, it in enumerate((i0, i1, i2, i3)):
                self.syntax_table.setItem(r_idx, c_idx, it)

    # =========================================================================
    # 子页 3：快捷键速查表
    # =========================================================================
    def _build_shortcuts_reference_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        lbl = QLabel("⌨️ 全局与工作台快捷键实时速查表（支持在「设置 ➔ 快捷键设置」中自由修改）")
        lbl.setProperty("sectionTitle", True)
        top_bar.addWidget(lbl)
        top_bar.addStretch()

        self.edit_sc_search = QLineEdit()
        self.edit_sc_search.setPlaceholderText("搜索快捷键或功能名称...")
        self.edit_sc_search.setMaximumWidth(260)
        self.edit_sc_search.textChanged.connect(self._refresh_shortcut_table)
        top_bar.addWidget(self.edit_sc_search)

        btn_edit_sc = QPushButton("⚙️ 前往自定义修改快捷键")
        btn_edit_sc.setIcon(CartoonIconManager.get_icon("act_keyboard"))
        btn_edit_sc.setProperty("primary", True)
        btn_edit_sc.clicked.connect(self.open_shortcut_settings_requested.emit)
        top_bar.addWidget(btn_edit_sc)

        layout.addLayout(top_bar)

        self.shortcut_table = QTableWidget(0, 5)
        self.shortcut_table.setHorizontalHeaderLabels(
            ["所属分类", "功能名称", "当前生效快捷键", "系统默认键位", "功能详细说明"]
        )
        self.shortcut_table.verticalHeader().setVisible(False)
        self.shortcut_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.shortcut_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.shortcut_table.setAlternatingRowColors(True)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.shortcut_table, 1)

        return page

    def _refresh_shortcut_table(self) -> None:
        cfg = self.controller.app_config
        kw = self.edit_sc_search.text().strip().lower() if hasattr(self, "edit_sc_search") else ""
        filtered = [
            d for d in SHORTCUT_DEFINITIONS
            if not kw
            or kw in d.category.lower()
            or kw in d.title.lower()
            or kw in d.description.lower()
            or kw in cfg.get_shortcut(d.action_id).lower()
        ]
        self.shortcut_table.setRowCount(len(filtered))
        key_font = QFont("Consolas", 10, QFont.Bold)
        for r_idx, d in enumerate(filtered):
            self.shortcut_table.setRowHeight(r_idx, 32)
            cur_key = cfg.get_shortcut(d.action_id) or "未绑定"
            i0 = QTableWidgetItem(d.category)
            i0.setTextAlignment(Qt.AlignCenter)
            i1 = QTableWidgetItem(d.title)
            i2 = QTableWidgetItem(f"  {cur_key}  ")
            i2.setFont(key_font)
            i2.setForeground(QColor("#1D4ED8"))
            i2.setTextAlignment(Qt.AlignCenter)
            i3 = QTableWidgetItem(d.default_key)
            i3.setTextAlignment(Qt.AlignCenter)
            i4 = QTableWidgetItem(d.description)
            for c_idx, it in enumerate((i0, i1, i2, i3, i4)):
                self.shortcut_table.setItem(r_idx, c_idx, it)

    # =========================================================================
    # 子页 4：吃码风控与算账公式详解
    # =========================================================================
    def _build_formula_and_risk_page(self) -> QWidget:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("QTextBrowser { padding: 14px; font-size: 13.5px; line-height: 1.65; }")
        browser.setHtml(
            """
            <h2 style="color:#1E3A8A;">🛡️ 核心风控与财务算账公式全解析</h2>
            <p>本系统严格遵循原版 Excel 宏工作簿的数学精算逻辑，并采用 64 位高精度浮点与二分逼近算法实现毫秒级实时重算：</p>
            <hr>
            <h3 style="color:#2563EB;">1. 单号全盘风险值（不做吃码时的净风险）</h3>
            <p>设全盘 1–49 号总收单金额为 <b>TotalPool</b>，统一赔率为 <b>Odds</b>（如 47 倍），统一回水比例为 <b>Rebate</b>（如 2% = 0.02），某个号码 <i>i</i> 的总收单押注为 <b>Bet(i)</b>：</p>
            <ul>
              <li><b>全盘净实收本金（扣除回水后）</b> = <code>TotalPool × (1 - Rebate)</code></li>
              <li><b>号码 i 中奖赔付总额</b> = <code>Bet(i) × Odds</code></li>
              <li><b>号码 i 风险值</b> = <code>Bet(i) × Odds - TotalPool × (1 - Rebate)</code></li>
              <li>📌 <b>直观解读</b>：
                <ul>
                  <li>当风险值 <b>&gt; 0（红色预警）</b>：表示若本期开出该特码，庄家赔付后将<b>净亏损</b>该金额；</li>
                  <li>当风险值 <b>&le; 0（安全绿色）</b>：表示若本期开出该特码，庄家不仅够赔，还能<b>净盈利</b>该绝对值金额！</li>
                </ul>
              </li>
            </ul>

            <h3 style="color:#2563EB;">2. 吃码留存与飞单上报拆分公式</h3>
            <p>设号码 <i>i</i> 的总汇总为 <b>Total(i)</b>，已经归档上报给上庄的金额为 <b>Reported(i)</b>，您设定的单号自己吃上限为 <b>EatLimit</b>：</p>
            <ul>
              <li><b>尚未上报的可用池 Remaining(i)</b> = <code>max(0, Total(i) - Reported(i))</code></li>
              <li><b>自己吃金额 Eat(i)</b> = <code>min(Remaining(i), EatLimit)</code></li>
              <li><b>本次预备上报金额 Report(i)</b> = <code>Remaining(i) - Eat(i)</code></li>
              <li><b>吃码后留存风险值 EatRisk(i)</b> = <code>Eat(i) × Odds - TotalEatPool × (1 - Rebate)</code></li>
            </ul>

            <h3 style="color:#2563EB;">3. 「设定最大亏损反推最佳吃码额」二分算法原理</h3>
            <p>当您在【吃码上报】页输入<b>「允许最大亏损金额 MaxLoss（如 3000 元）」</b>时：</p>
            <ul>
              <li>系统以最高押注号码的吃码后风险值等于 <code>MaxLoss</code> 为目标方程，在区间 <code>[0, 最大单号剩余额]</code> 内执行高精度二分搜索；</li>
              <li>自动求出既能让您留存最多本金、又能严格保证<b>无论开出哪一个特码，您的最大净亏损绝不超过设定上限</b>的最佳单号吃码线！</li>
            </ul>

            <h3 style="color:#2563EB;">4. 开奖后分人算账与回水结算公式</h3>
            <p>针对每位收单客户 <i>c</i>（拥有独立赔率 <b>Odds(c)</b> 与独立回水比例 <b>Rebate(c)</b>），当开出特码 <b>W</b> 时：</p>
            <ul>
              <li><b>客户总押注</b> = <code>SumBet(c)</code>；<b>客户买中特码 W 的金额</b> = <code>WinBet(c)</code></li>
              <li><b>客户中码奖金</b> = <code>WinBet(c) × Odds(c)</code></li>
              <li><b>客户回水金额</b> = <code>SumBet(c) × Rebate(c)</code></li>
              <li><b>盈亏（不包回水）</b> = <code>SumBet(c) - WinBet(c) × Odds(c)</code></li>
              <li><b>庄家对该客户净盈亏（含回水）</b> = <code>SumBet(c) - WinBet(c) × Odds(c) - SumBet(c) × Rebate(c)</code></li>
            </ul>
            """
        )
        return browser

    # =========================================================================
    # 子页 5：常见问题与数据安全指南 (FAQ)
    # =========================================================================
    def _build_faq_and_safety_page(self) -> QWidget:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("QTextBrowser { padding: 14px; font-size: 13.5px; line-height: 1.65; }")
        db_path = self.controller.db_manager.db_path
        browser.setHtml(
            f"""
            <h2 style="color:#1E3A8A;">❓ 常见问题解答 (FAQ) 与新用户分发/迁移指南</h2>
            <p>📍 <b>当前正在使用的本地数据库文件位置：</b> <code>{db_path}</code></p>
            <hr>

            <h3 style="color:#2563EB;">Q1：我把这个 .exe 文件单独发给新用户，对方电脑什么环境都没装能直接用吗？</h3>
            <p><b>答：完全可以！100% 开箱即用。</b><br>
            本程序已将 Python 运行时、PyQt5 界面渲染引擎、全套 44 枚卡通高清图标以及 1,955+ 默认识别词库全部封装在单个 <code>.exe</code> 内部。新用户收到后无论放在桌面还是任意目录，双击即可直接运行。</p>

            <h3 style="color:#2563EB;">Q2：软件的数据保存在哪里？会在桌面或 .exe 旁边生成多余的文件夹吗？</h3>
            <p><b>答：严格遵循 Windows 规范，绝不在桌面或 .exe 同级目录产生任何杂乱文件！</b><br>
            所有本地数据库与配置文件默认安全存放在 Windows 系统当前用户数据目录：<code>%LOCALAPPDATA%\\LotteryRiskPro\\data\\lottery_system.db</code>。<br>
            这样不仅保持您的桌面干净整洁，而且当您移动 <code>.exe</code> 位置或直接替换升级新版 <code>.exe</code> 时，原有的客户档案、订单与配置 <b>100% 自动保留</b>！您也可以在「系统设置 ➔ 本地数据库备份与维护」中点击「📁 打开系统用户数据目录 (AppData)」一键查看。</p>

            <h3 style="color:#2563EB;">Q3：如何更换电脑或备份我的客户档案、词库与订单数据？</h3>
            <p><b>答：按快捷键 Ctrl+B 一键备份即可！</b></p>
            <ol>
              <li><b>一键导出备份</b>：按快捷键 <b>Ctrl+B</b>（或在「设置 ➔ 本地数据库备份与维护」中点击一键备份），即可将全部数据导出为单个 <code>.db</code> 备份文件；</li>
              <li><b>新电脑一键恢复</b>：在新电脑上打开本软件，进入「设置 ➔ 本地数据库备份与维护」点击「📂 从备份文件恢复 SQLite 数据库」即可完整还原。</li>
            </ol>

            <h3 style="color:#2563EB;">Q4：跨年了（比如从马年进入羊年），12 生肖对应的号码变了怎么办？</h3>
            <p><b>答：只需 1 秒切换！</b><br>
            前往<b>【系统设置 ➔ 全局识别与参数配置】</b>，将「当前农历本命年生肖」从「马」切换为「羊」（或任意生肖）并点击保存，全系统 1–49 号的生肖映射、主肖/平肖识别规则及顶部本命年萌宠徽章会立即自动重新推算并生效！</p>

            <h3 style="color:#2563EB;">Q5：客户发来的微信报单里有特殊的方言或简称（比如把“各10元”发成“十米”），怎么让软件自动识别？</h3>
            <p><b>答：支持自定义词库与自定义替换规则！</b></p>
            <ul>
              <li>在<b>【系统设置 ➔ 智能识别词库】</b>中，您可以随时向「各字」「共字」「单数」「双数」等分类添加新词条；</li>
              <li>或者在<b>【系统设置 ➔ 自定义替换规则与号码属性】</b>中，添加一条查找替换规则（如查找 <code>一米</code> 替换为 <code>各1</code>），识别时会自动预先转换！</li>
            </ul>
            """
        )
        return browser

    def refresh_data(self) -> None:
        """刷新快捷键速查表，确保与用户在设置页自定义的键位实时同步"""
        if hasattr(self, "shortcut_table"):
            self._refresh_shortcut_table()
