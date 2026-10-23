"""
核心领域模型与值对象 (Domain Entities & Value Objects)
采用面向对象设计思想，封装业务实体属性与领域计算逻辑
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from typing import Any, Dict, List, Optional, Tuple

from src.version import OFFICIAL_GITHUB_REPO, DEFAULT_UPDATE_SOURCE_MODE


@dataclass(frozen=True)
class ShortcutDefinition:
    """系统可自定义快捷键元数据定义"""
    action_id: str
    category: str
    title: str
    description: str
    default_key: str


SHORTCUT_DEFINITIONS: Tuple[ShortcutDefinition, ...] = (
    # 1. 页面导航快捷键
    ShortcutDefinition("switch_tab_1", "页面导航", "切换至「主控看板」", "快速打开 1-49 号码实时风险监控看板", "Alt+1"),
    ShortcutDefinition("switch_tab_2", "页面导航", "切换至「微信智能收单」", "快速打开微信/QQ聊天记录识别与极速录单台", "Alt+2"),
    ShortcutDefinition("switch_tab_3", "页面导航", "切换至「吃码上报风控」", "快速打开吃码二分反推与多上庄飞单上报页", "Alt+3"),
    ShortcutDefinition("switch_tab_4", "页面导航", "切换至「开奖对奖算账」", "快速打开特码开奖对奖、订单明细与分人结账页", "Alt+4"),
    ShortcutDefinition("switch_tab_history", "页面导航", "切换至「历史日期回看」", "快速打开按日期/日期区间历史回看与期数复盘中心", "Alt+6"),
    ShortcutDefinition("switch_tab_5", "页面导航", "切换至「系统设置中心」", "快速打开系统参数、客户赔率、词库与快捷键设置", "Alt+5"),
    ShortcutDefinition("switch_tab_6", "页面导航", "打开「使用说明与指南」", "随时呼出图文使用教程、报单口语大全与快捷键表", "F1"),
    # 2. 微信收单与录单快捷键
    ShortcutDefinition("parse_wechat", "微信收单与录单", "立即识别微信报单文本", "对输入框内的微信/QQ报单内容执行智能解析", "Ctrl+Return"),
    ShortcutDefinition("submit_order", "微信收单与录单", "确认入库识别结果", "将当前预览表中的有效押注一键写入当前客户账本", "F2"),
    ShortcutDefinition("paste_and_parse", "微信收单与录单", "一键粘贴并立即识别", "读取系统剪贴板最新文本并自动填入解析", "Ctrl+Shift+V"),
    ShortcutDefinition("clear_wechat_input", "微信收单与录单", "清空微信输入框与预览", "一键清空当前微信报单输入框及下方预览列表", "Ctrl+L"),
    ShortcutDefinition("negate_parsed", "微信收单与录单", "识别结果一键转负数(减单)", "将预览表中的正数金额转为负数，用于客户退单冲正", "Ctrl+M"),
    ShortcutDefinition("focus_quick_input", "微信收单与录单", "聚焦「极速盲打录入框」", "将光标直接定位到右侧单号/多号极速盲打输入框", "F3"),
    # 3. 吃码风控与开奖算账快捷键
    ShortcutDefinition("copy_eat_report", "吃码与开奖算账", "一键复制预备上报散码", "将吃码风控页计算好的预备上报散码复制到剪贴板", "Ctrl+Shift+C"),
    ShortcutDefinition("run_settlement", "吃码与开奖算账", "立即执行特码对奖算账", "根据所选开奖特码立即核算全盘与各客户净盈亏", "F8"),
    ShortcutDefinition("copy_settlement_bill", "吃码与开奖算账", "一键复制分人结账汇总单", "将开奖后的分人结算账单复制到剪贴板以便发群", "Ctrl+Shift+B"),
    # 4. 全局系统与数据快捷操作
    ShortcutDefinition("quick_add_client", "全局系统操作", "快速新增收单客户", "弹窗在当前盘口下快速新建一位收单客户档案", "Ctrl+N"),
    ShortcutDefinition("rename_current_client", "全局系统操作", "修正当前客户名称", "弹窗修改或更正当前收单客户名称并同步其历史订单", "F4"),
    ShortcutDefinition("export_excel", "全局系统操作", "导出完整 Excel 报表", "将当前盘口汇总、风险表、算账单与明细导出为 .xlsx", "Ctrl+E"),
    ShortcutDefinition("backup_database", "全局系统操作", "立即备份本地数据库", "将本地 SQLite 数据库一键备份为独立 .db 文件", "Ctrl+B"),
    ShortcutDefinition("toggle_theme", "全局系统操作", "切换亮色 / 暗色护眼主题", "在现代浅色主题与深邃暗夜护眼主题之间一键切换", "Ctrl+T"),
    ShortcutDefinition("refresh_all", "全局系统操作", "全局刷新所有看板数据", "强制重新同步并刷新全部六个工作台页面与状态栏", "F5"),
    ShortcutDefinition("check_update", "全局系统操作", "检查软件版本更新", "立即连接 Git 仓库或自定义更新服务器检查新版本", "Ctrl+U"),
)

DEFAULT_SHORTCUTS: Dict[str, str] = {item.action_id: item.default_key for item in SHORTCUT_DEFINITIONS}


class BetMode(str, Enum):
    """识别版本模式（对应原全局变量表：版本号）"""
    EACH_NUMBER = "各号版"
    EACH_ZODIAC_SINGLE_ZODIAC = "各肖版_单肖各肖"
    EACH_ZODIAC_SINGLE_NUM = "各肖版_单肖各号"


class SuiMode(str, Enum):
    """岁数识别模式（对应原全局变量表：岁模式）"""
    SUI_EACH = "岁模式_各"
    SUI_ZODIAC = "岁模式_生肖"


class CopyFormat(str, Enum):
    """吃码上报复制格式"""
    SPACE = "复制格式_空格"
    COMMA = "复制格式_逗号"


class DefaultBetStyle(str, Enum):
    """选号下单默认方式"""
    ZODIAC_FLAT = "生肖平摊"
    ZODIAC_EACH_NUM = "生肖每个号"


@dataclass
class AppConfig:
    """全局用户可自定义配置实体"""
    base_zodiac: str = "马"  # 当前本命年生肖（如马年，决定1-49号对应的12生肖）
    bet_mode: BetMode = BetMode.EACH_NUMBER
    recognize_decimal: bool = True
    auto_copy_parse: bool = False
    auto_switch_to_wechat_on_copy: bool = True
    confirm_before_clear: bool = True
    default_bet_style: DefaultBetStyle = DefaultBetStyle.ZODIAC_FLAT
    auto_save_seconds: int = 30
    sui_mode: SuiMode = SuiMode.SUI_EACH
    report_copy_format: CopyFormat = CopyFormat.SPACE
    error_popup: bool = True
    show_client_data: bool = True
    replace_newline_in_box: bool = True
    theme_mode: str = "light"  # "light" or "dark"
    update_source_mode: str = DEFAULT_UPDATE_SOURCE_MODE  # 写死锁定官方源 "github_api"
    update_repo_or_url: str = OFFICIAL_GITHUB_REPO        # 写死锁定官方源 "suncore946/Smar-Payment-System"
    update_mirror_prefix: str = ""
    auto_check_update_on_startup: bool = True
    skipped_version: str = ""
    shortcuts: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SHORTCUTS))

    def get_shortcut(self, action_id: str) -> str:
        """获取指定动作的当前快捷键，若未设置则返回默认快捷键"""
        return self.shortcuts.get(action_id, DEFAULT_SHORTCUTS.get(action_id, ""))

    def reset_shortcuts(self) -> None:
        """恢复全部快捷键为系统默认值"""
        self.shortcuts = dict(DEFAULT_SHORTCUTS)

    def to_dict(self) -> Dict[str, str]:
        return {
            "base_zodiac": self.base_zodiac,
            "bet_mode": self.bet_mode.value,
            "recognize_decimal": "1" if self.recognize_decimal else "0",
            "auto_copy_parse": "1" if self.auto_copy_parse else "0",
            "auto_switch_to_wechat_on_copy": "1" if self.auto_switch_to_wechat_on_copy else "0",
            "confirm_before_clear": "1" if self.confirm_before_clear else "0",
            "default_bet_style": self.default_bet_style.value,
            "auto_save_seconds": str(self.auto_save_seconds),
            "sui_mode": self.sui_mode.value,
            "report_copy_format": self.report_copy_format.value,
            "error_popup": "1" if self.error_popup else "0",
            "show_client_data": "1" if self.show_client_data else "0",
            "replace_newline_in_box": "1" if self.replace_newline_in_box else "0",
            "theme_mode": self.theme_mode,
            "update_source_mode": self.update_source_mode,
            "update_repo_or_url": self.update_repo_or_url,
            "update_mirror_prefix": self.update_mirror_prefix,
            "auto_check_update_on_startup": "1" if self.auto_check_update_on_startup else "0",
            "skipped_version": self.skipped_version,
            "shortcuts_json": json.dumps(self.shortcuts, ensure_ascii=False),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "AppConfig":
        cfg = cls()
        if "base_zodiac" in data and data["base_zodiac"]:
            cfg.base_zodiac = data["base_zodiac"]
        if "bet_mode" in data:
            for m in BetMode:
                if m.value == data["bet_mode"]:
                    cfg.bet_mode = m
                    break
        if "recognize_decimal" in data:
            cfg.recognize_decimal = data["recognize_decimal"] in ("1", "True", "true", "识别小数点_是")
        if "auto_copy_parse" in data:
            cfg.auto_copy_parse = data["auto_copy_parse"] in ("1", "True", "true", "自动复制_是")
        if "auto_switch_to_wechat_on_copy" in data:
            cfg.auto_switch_to_wechat_on_copy = data["auto_switch_to_wechat_on_copy"] in ("1", "True", "true")
        if "confirm_before_clear" in data:
            cfg.confirm_before_clear = data["confirm_before_clear"] in ("1", "True", "true")
        if "default_bet_style" in data:
            for s in DefaultBetStyle:
                if s.value == data["default_bet_style"]:
                    cfg.default_bet_style = s
                    break
        if "auto_save_seconds" in data:
            try:
                cfg.auto_save_seconds = max(5, int(float(data["auto_save_seconds"])))
            except ValueError:
                cfg.auto_save_seconds = 30
        if "sui_mode" in data:
            for sm in SuiMode:
                if sm.value == data["sui_mode"]:
                    cfg.sui_mode = sm
                    break
        if "report_copy_format" in data:
            for cf in CopyFormat:
                if cf.value == data["report_copy_format"]:
                    cfg.report_copy_format = cf
                    break
        if "error_popup" in data:
            cfg.error_popup = data["error_popup"] in ("1", "True", "true", "错误是否弹窗_是")
        if "show_client_data" in data:
            cfg.show_client_data = data["show_client_data"] in ("1", "True", "true", "显示下单人数据_是")
        if "replace_newline_in_box" in data:
            cfg.replace_newline_in_box = data["replace_newline_in_box"] in ("1", "True", "true")
        if "theme_mode" in data and data["theme_mode"] in ("light", "dark"):
            cfg.theme_mode = data["theme_mode"]
        if "update_source_mode" in data and data["update_source_mode"]:
            loaded_mode = data["update_source_mode"]
            # 官方源锁定：除非是本地文件测试模式，否则一律锁定为官方 github_api
            cfg.update_source_mode = loaded_mode if loaded_mode == "github_or_json" else "github_api"
        if "update_repo_or_url" in data and data["update_repo_or_url"] is not None:
            loaded_url = data["update_repo_or_url"].strip()
            # 允许本地文件/测试用例路径；其余远程地址强制锁定为官方 GitHub 仓库防篡改
            if loaded_url.endswith(".json") or ("/" not in loaded_url and "\\" in loaded_url):
                cfg.update_repo_or_url = loaded_url
            else:
                cfg.update_repo_or_url = OFFICIAL_GITHUB_REPO
        else:
            cfg.update_repo_or_url = OFFICIAL_GITHUB_REPO
        if "update_mirror_prefix" in data and data["update_mirror_prefix"] is not None:
            cfg.update_mirror_prefix = data["update_mirror_prefix"]
        if "auto_check_update_on_startup" in data:
            cfg.auto_check_update_on_startup = data["auto_check_update_on_startup"] in ("1", "True", "true")
        if "skipped_version" in data and data["skipped_version"] is not None:
            cfg.skipped_version = data["skipped_version"]
        if "shortcuts_json" in data and data["shortcuts_json"]:
            try:
                loaded_sc = json.loads(data["shortcuts_json"])
                if isinstance(loaded_sc, dict):
                    merged = dict(DEFAULT_SHORTCUTS)
                    for k, v in loaded_sc.items():
                        if isinstance(k, str) and isinstance(v, str):
                            merged[k] = v
                    cfg.shortcuts = merged
            except Exception:
                cfg.shortcuts = dict(DEFAULT_SHORTCUTS)
        return cfg


@dataclass
class RegionConfig:
    """盘口/地区配置实体（如：新澳门、旧澳门、香港）"""
    name: str
    display_order: int = 1
    global_odds: float = 47.0
    global_rebate: float = 0.02
    active_client_name: str = ""
    last_winning_number: int = 0


@dataclass
class ClientProfile:
    """下单人/客户领域实体"""
    id: Optional[int]
    region: str
    name: str
    odds: float = 47.0
    rebate: float = 0.0
    sort_order: int = 1
    number_bets: Dict[int, float] = field(default_factory=lambda: {i: 0.0 for i in range(1, 50)})

    @property
    def total_bet(self) -> float:
        return round(sum(self.number_bets.values()), 2)

    def get_bet(self, number: int) -> float:
        return round(self.number_bets.get(number, 0.0), 2)


@dataclass
class ParsedBetItem:
    """微信/QQ智能识别出的单条押注项值对象"""
    numbers: List[int]
    per_number_amount: float
    total_amount: float
    raw_fragment: str = ""
    is_valid: bool = True
    error_message: str = ""

    @property
    def formatted_numbers(self) -> str:
        return ",".join(f"{n:02d}" if 1 <= n <= 49 else str(n) for n in self.numbers)

    @property
    def count(self) -> int:
        return len(self.numbers)

    @property
    def canonical_expression(self) -> str:
        """转化为标准押注内容格式，例如 '04,16,28,40各25'"""
        amt_str = f"{self.per_number_amount:g}"
        return f"{self.formatted_numbers}各{amt_str}"

    def validate(self) -> bool:
        if not self.numbers:
            self.is_valid = False
            self.error_message = "未识别到号码"
            return False
        if self.per_number_amount == 0:
            self.is_valid = False
            self.error_message = "金额为0"
            return False
        for n in self.numbers:
            if n < 1 or n > 49:
                self.is_valid = False
                self.error_message = f"非法号码: {n}"
                return False
        self.is_valid = True
        self.error_message = ""
        return True


@dataclass
class OrderRecord:
    """订单明细记录实体"""
    id: Optional[int]
    seq_no: int
    region: str
    client_name: str
    raw_text: str
    parsed_content: str
    total_amount: float
    winning_amount: float = 0.0
    pnl_no_rebate: float = 0.0
    rebate_amount: float = 0.0
    net_pnl: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class RiskItem:
    """单号码(01-49)汇总、吃码、上报与风险计算实体"""
    number: int
    zodiac: str
    wave_color: str  # "red", "blue", "green"
    total_bet: float = 0.0
    eat_amount: float = 0.0
    report_amount: float = 0.0
    reported_amount: float = 0.0
    full_risk_value: float = 0.0
    eat_risk_value: float = 0.0

    @property
    def number_str(self) -> str:
        return f"{self.number:02d}"

    @property
    def remaining_pool(self) -> float:
        """尚未上报的可用汇总池 = 汇总 - 已经上报"""
        return max(0.0, round(self.total_bet - self.reported_amount, 2))


@dataclass
class BookmakerRecord:
    """上庄上报记录实体"""
    id: Optional[int]
    region: str
    name: str
    report_text: str = ""
    reported_map: Dict[int, float] = field(default_factory=dict)
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def total_reported(self) -> float:
        return round(sum(self.reported_map.values()), 2)


@dataclass
class ClientSettlementItem:
    """开奖对奖算账时单个客户的结算结果值对象"""
    client_name: str
    odds: float
    rebate: float
    total_bet: float
    winning_bet: float
    pnl_no_rebate: float
    rebate_amount: float
    net_pnl: float
    order_count: int = 0


@dataclass
class ReplaceRule:
    """自定义文字替换规则实体"""
    id: Optional[int]
    find_text: str
    replace_text: str
    is_enabled: bool = True
    description: str = ""


@dataclass
class DailyTrendItem:
    """按日期聚合的每日收单与盈亏趋势值对象"""
    date_str: str
    order_count: int
    client_count: int
    total_bet: float
    winning_payout: float
    rebate_amount: float
    net_pnl: float
    top_number: int = 0
    top_number_bet: float = 0.0


@dataclass
class DailyArchiveRecord:
    """每日/每期完整账目归档快照实体（防止清盘后历史数据丢失，支持随时按日期回看或还原）"""
    id: Optional[int]
    archive_date: str  # YYYY-MM-DD
    region: str
    title: str
    winning_number: int
    base_zodiac: str
    total_bet: float
    total_winning: float
    total_rebate: float
    net_pnl: float
    order_count: int
    client_count: int
    orders_data: List[Dict[str, Any]] = field(default_factory=list)
    settlements_data: List[Dict[str, Any]] = field(default_factory=list)
    risk_data: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class DateRangeReviewSummary:
    """按单日或任意起止日期区间回看的全维度复盘汇总值对象"""
    start_date: str
    end_date: str
    region: str
    simulated_winning_number: int
    total_orders: int
    active_days_count: int
    active_clients_count: int
    total_bet: float
    total_winning_payout: float
    total_rebate: float
    total_net_pnl: float
    top_number: int
    top_number_bet: float
    number_bets: Dict[int, float] = field(default_factory=lambda: {i: 0.0 for i in range(1, 50)})
    risk_items: List[RiskItem] = field(default_factory=list)
    client_settlements: List[ClientSettlementItem] = field(default_factory=list)
    orders: List[OrderRecord] = field(default_factory=list)
    daily_trends: List[DailyTrendItem] = field(default_factory=list)
