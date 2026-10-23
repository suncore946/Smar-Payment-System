"""
风险监控与吃码上报风控服务 (RiskAndEatService)
完整复刻并增强原 Excel 主表风险值排序、`吃码上报.frm`、`吃码上报_模块.bas`、
按平均吃码、按最大亏损二分反推吃码、按比例/按号/按属性吃码上报、以及多上庄保存与撤回逻辑。
"""

from __future__ import annotations
from datetime import datetime
import math
from typing import Dict, List, Optional, Tuple
from src.database.repositories import ClientRepository, EatReportRepository, RegionRepository
from src.domain.attribute_engine import NumberAttributeEngine
from src.domain.models import BookmakerRecord, CopyFormat, RiskItem


class RiskAndEatService:
    """面向对象吃码、上报与实时风险计算服务"""

    DEFAULT_BOOKMAKERS = ["上庄张", "上庄李", "上庄王", "上庄周", "上庄吴"]

    def __init__(
        self,
        attr_engine: NumberAttributeEngine,
        region_repo: RegionRepository,
        client_repo: ClientRepository,
        eat_repo: EatReportRepository,
    ) -> None:
        self.attr_engine = attr_engine
        self.region_repo = region_repo
        self.client_repo = client_repo
        self.eat_repo = eat_repo

    @staticmethod
    def calculate_risk_value(total_pool: float, number_bet: float, odds: float, rebate: float) -> float:
        """
        计算单个号码的风险值（庄家视角盈亏）：
        风险值 = 总收单金额 * (1 - 回水) - 该号押注金额 * 赔率
        正数表示开出该号时庄家盈利（盈余），负数表示开出该号时庄家亏损。
        """
        return round(total_pool * (1.0 - rebate) - number_bet * odds, 2)

    def get_region_risk_items(self, region: str) -> List[RiskItem]:
        """获取指定盘口 1-49 号的完整汇总、吃码、上报与风险计算对象列表"""
        reg_cfg = self.region_repo.get_region(region)
        odds = reg_cfg.global_odds if reg_cfg else 47.0
        rebate = reg_cfg.global_rebate if reg_cfg else 0.02

        totals_by_num = self.client_repo.get_region_total_bets_by_number(region)
        eat_state = self.eat_repo.get_eat_report_state(region)

        full_pool = round(sum(totals_by_num.values()), 2)

        # 第一遍确定每个号码的实际有效吃码与待上报金额
        effective_eats: Dict[int, float] = {}
        pending_reports: Dict[int, float] = {}
        reported_map: Dict[int, float] = {}

        for num in range(1, 50):
            tot = round(totals_by_num.get(num, 0.0), 2)
            eat_amt, _, reported_amt = eat_state.get(num, (0.0, 0.0, 0.0))
            reported_amt = max(0.0, min(tot, round(reported_amt, 2)))
            avail = max(0.0, round(tot - reported_amt, 2))
            eff_eat = max(0.0, min(avail, round(eat_amt, 2)))
            rep_amt = max(0.0, round(avail - eff_eat, 2))

            effective_eats[num] = eff_eat
            pending_reports[num] = rep_amt
            reported_map[num] = reported_amt

        eat_pool = round(sum(effective_eats.values()), 2)

        items: List[RiskItem] = []
        for num in range(1, 50):
            tot = round(totals_by_num.get(num, 0.0), 2)
            eff_eat = effective_eats[num]
            rep_amt = pending_reports[num]
            reported_amt = reported_map[num]

            full_risk = self.calculate_risk_value(full_pool, tot, odds, rebate)
            eat_risk = self.calculate_risk_value(eat_pool, eff_eat, odds, rebate)

            items.append(
                RiskItem(
                    number=num,
                    zodiac=self.attr_engine.get_zodiac_of_number(num),
                    wave_color=self.attr_engine.get_wave_color(num),
                    total_bet=tot,
                    eat_amount=eff_eat,
                    report_amount=rep_amt,
                    reported_amount=reported_amt,
                    full_risk_value=full_risk,
                    eat_risk_value=eat_risk,
                )
            )
        return items

    def get_sorted_risk_ranking(self, region: str, by_eat: bool = False) -> List[RiskItem]:
        """
        按金额从高到低（即风险从高到低/盈亏从小到大）排序返回 1-49 号排行
        """
        items = self.get_region_risk_items(region)
        if by_eat:
            return sorted(items, key=lambda x: (x.eat_risk_value, -x.eat_amount, x.number))
        return sorted(items, key=lambda x: (-x.total_bet, x.full_risk_value, x.number))

    def apply_average_eat(self, region: str, avg_eat_cap: float) -> List[RiskItem]:
        """
        按平均吃码上限设置吃码（对应原 `打算平均吃码` / `吃码范围_Scroll`）：
        每个号码最多吃 `avg_eat_cap`，超出部分自动转入 `预备上报`
        """
        avg_eat_cap = max(0.0, round(avg_eat_cap, 2))
        items = self.get_region_risk_items(region)
        new_state: Dict[int, Tuple[float, float, float]] = {}
        for item in items:
            avail = item.remaining_pool
            eat_val = min(avail, avg_eat_cap)
            rep_val = max(0.0, round(avail - eat_val, 2))
            new_state[item.number] = (eat_val, rep_val, item.reported_amount)
        self.eat_repo.save_eat_report_state(region, new_state)
        return self.get_region_risk_items(region)

    def apply_max_loss_eat(self, region: str, max_allowed_loss: float) -> Tuple[float, List[RiskItem]]:
        """
        按最大允许亏损金额反推最佳平均吃码上限（对应原 `打算最多亏_KeyUp` 的二分查找算法）：
        寻找最大的单号吃码上限 `cap`，使得最坏情况下的亏损不超过 `max_allowed_loss`。
        返回 `(optimal_cap, updated_items)`
        """
        max_allowed_loss = max(0.0, float(max_allowed_loss))
        reg_cfg = self.region_repo.get_region(region)
        odds = reg_cfg.global_odds if reg_cfg else 47.0
        rebate = reg_cfg.global_rebate if reg_cfg else 0.02

        items = self.get_region_risk_items(region)
        max_avail = max((it.remaining_pool for it in items), default=0.0)
        if max_avail <= 0:
            return 0.0, items

        left = 0
        right = int(math.ceil(max_avail))
        while left < right:
            mid = left + math.ceil((right - left) / 2)
            eat_pool = sum(min(it.remaining_pool, float(mid)) for it in items)
            risk_val = round(eat_pool * (1.0 - rebate) - float(mid) * odds, 2)
            if risk_val >= -max_allowed_loss:
                left = mid
            else:
                right = mid - 1

        optimal_cap = float(left)
        updated = self.apply_average_eat(region, optimal_cap)
        return optimal_cap, updated

    def apply_percentage_eat(self, region: str, eat_percent: float) -> List[RiskItem]:
        """
        按比例吃码（例如吃 30%，则上报 70%）：
        `eat_percent` 取值 0~100
        """
        ratio = max(0.0, min(100.0, float(eat_percent))) / 100.0
        items = self.get_region_risk_items(region)
        new_state: Dict[int, Tuple[float, float, float]] = {}
        for item in items:
            avail = item.remaining_pool
            eat_val = round(avail * ratio, 2)
            rep_val = max(0.0, round(avail - eat_val, 2))
            new_state[item.number] = (eat_val, rep_val, item.reported_amount)
        self.eat_repo.save_eat_report_state(region, new_state)
        return self.get_region_risk_items(region)

    def apply_percentage_report(self, region: str, report_percent: float) -> List[RiskItem]:
        """
        按比例上报（例如上报 60%，则自己吃 40%）：
        `report_percent` 取值 0~100
        """
        eat_pct = 100.0 - max(0.0, min(100.0, float(report_percent)))
        return self.apply_percentage_eat(region, eat_pct)

    def apply_numbers_eat_or_report(
        self,
        region: str,
        numbers: List[int],
        amount: float,
        mode: str = "eat",
    ) -> List[RiskItem]:
        """
        按指定号码集合或生肖属性设置吃码或上报金额：
        - mode == "eat": 设置这些号码的吃码额为 min(可用汇总, amount)
        - mode == "report": 设置这些号码的预备上报额为 min(可用汇总, amount)
        """
        target_set = set(numbers)
        amount = max(0.0, round(float(amount), 2))
        items = self.get_region_risk_items(region)
        new_state: Dict[int, Tuple[float, float, float]] = {}
        for item in items:
            avail = item.remaining_pool
            if item.number in target_set:
                if mode == "eat":
                    eat_val = min(avail, amount)
                    rep_val = max(0.0, round(avail - eat_val, 2))
                else:
                    rep_val = min(avail, amount)
                    eat_val = max(0.0, round(avail - rep_val, 2))
                new_state[item.number] = (eat_val, rep_val, item.reported_amount)
            else:
                new_state[item.number] = (item.eat_amount, item.report_amount, item.reported_amount)
        self.eat_repo.save_eat_report_state(region, new_state)
        return self.get_region_risk_items(region)

    def clear_all_eat(self, region: str) -> List[RiskItem]:
        """撤销所有吃码（吃码清零，全部未上报汇总归入预备上报）"""
        items = self.get_region_risk_items(region)
        new_state = {
            it.number: (0.0, it.remaining_pool, it.reported_amount)
            for it in items
        }
        self.eat_repo.save_eat_report_state(region, new_state)
        return self.get_region_risk_items(region)

    def update_single_number_eat(self, region: str, number: int, new_eat_amount: float) -> List[RiskItem]:
        """手动修改单个号码的吃码金额"""
        items = self.get_region_risk_items(region)
        new_state: Dict[int, Tuple[float, float, float]] = {}
        for it in items:
            if it.number == number:
                eat_val = max(0.0, min(it.remaining_pool, round(new_eat_amount, 2)))
                rep_val = max(0.0, round(it.remaining_pool - eat_val, 2))
                new_state[it.number] = (eat_val, rep_val, it.reported_amount)
            else:
                new_state[it.number] = (it.eat_amount, it.report_amount, it.reported_amount)
        self.eat_repo.save_eat_report_state(region, new_state)
        return self.get_region_risk_items(region)

    def format_copy_text(
        self,
        region: str,
        data_type: str = "上报",
        copy_format: CopyFormat = CopyFormat.SPACE,
        increase_percent: float = 0.0,
    ) -> str:
        """
        生成可一键复制到微信/剪贴板的散码文本（对应原 `吃码上报_模块.bas` -> `复制(类型)`）
        data_type: "上报" | "吃码" | "汇总" | "已经上报"
        increase_percent: 百分比增加金额（如 +10% 则乘以 1.1）
        """
        items = self.get_region_risk_items(region)
        sep = ", " if copy_format == CopyFormat.COMMA else " "
        factor = 1.0 + (increase_percent / 100.0)

        parts: List[str] = []
        total_sum = 0
        for it in items:
            if data_type == "吃码":
                val = it.eat_amount
            elif data_type == "汇总":
                val = it.total_bet
            elif data_type == "已经上报":
                val = it.reported_amount
            else:
                val = it.report_amount

            rounded = int(round(val * factor))
            if rounded > 0:
                parts.append(f"{it.number:02d}={rounded}")
                total_sum += rounded

        body = sep.join(parts)
        return f"{region}\n{data_type}数据明细：          {body}。合计：{total_sum}"

    def ensure_bookmakers(self, region: str) -> List[BookmakerRecord]:
        bms = self.eat_repo.list_bookmakers(region)
        if not bms:
            for name in self.DEFAULT_BOOKMAKERS:
                self.eat_repo.save_bookmaker(BookmakerRecord(id=None, region=region, name=name))
            bms = self.eat_repo.list_bookmakers(region)
        return bms

    def submit_report_to_bookmaker(self, region: str, bookmaker_name: str) -> BookmakerRecord:
        """
        将当前「预备上报」的数据正式提交保存给指定上庄，并转入「已经上报」池
        （对应 `吃码上报_保存或撤回上报.frm` -> `btm保存上报数据_Click`）
        """
        items = self.get_region_risk_items(region)
        bms = self.ensure_bookmakers(region)
        target_bm = next((b for b in bms if b.name == bookmaker_name), None)
        if not target_bm:
            target_bm = BookmakerRecord(id=None, region=region, name=bookmaker_name)

        new_state: Dict[int, Tuple[float, float, float]] = {}
        batch_lines: List[str] = []
        batch_total = 0.0
        count_in_row = 0
        row_buf: List[str] = []

        for it in items:
            prep = round(it.report_amount, 2)
            new_reported = round(it.reported_amount + prep, 2)
            new_state[it.number] = (it.eat_amount, 0.0, new_reported)
            if prep > 0:
                target_bm.reported_map[it.number] = round(target_bm.reported_map.get(it.number, 0.0) + prep, 2)
                batch_total = round(batch_total + prep, 2)
                row_buf.append(f"{it.number:02d}={prep:g}")
                count_in_row += 1
                if count_in_row % 7 == 0:
                    batch_lines.append("， ".join(row_buf))
                    row_buf = []
        if row_buf:
            batch_lines.append("， ".join(row_buf))

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_buf: List[str] = []
        sum_lines: List[str] = []
        sum_total = 0.0
        for num in range(1, 50):
            amt = round(target_bm.reported_map.get(num, 0.0), 2)
            if amt > 0:
                sum_total = round(sum_total + amt, 2)
                summary_buf.append(f"{num:02d}={amt:g}")
                if len(summary_buf) == 7:
                    sum_lines.append("， ".join(summary_buf))
                    summary_buf = []
        if summary_buf:
            sum_lines.append("， ".join(summary_buf))

        header_block = (
            f"上报汇总（{bookmaker_name}）：\n"
            + ("\n".join(sum_lines) if sum_lines else "（暂无）")
            + f"\n散码总数：{sum_total:g}\n"
            + ("*" * 60)
        )
        batch_block = f"\n上报时间：{now_str}\n上报散码数据：\n" + ("\n".join(batch_lines) if batch_lines else "（本次无新增上报）") + f"\n本次散码总数：{batch_total:g}\n"

        old_batches = ""
        if "*" * 60 in target_bm.report_text:
            old_batches = target_bm.report_text.split("*" * 60, 1)[1]

        target_bm.report_text = header_block + old_batches + batch_block
        target_bm.updated_at = now_str

        self.eat_repo.save_eat_report_state(region, new_state)
        self.eat_repo.save_bookmaker(target_bm)
        return target_bm

    def withdraw_bookmaker_report(self, region: str, bookmaker_name: str) -> None:
        """撤回指定上庄的上报数据，退回至预备上报（对应 `btn撤回当前上报数据_Click`）"""
        bms = self.ensure_bookmakers(region)
        target_bm = next((b for b in bms if b.name == bookmaker_name), None)
        if not target_bm or not target_bm.reported_map:
            return

        items = self.get_region_risk_items(region)
        new_state: Dict[int, Tuple[float, float, float]] = {}
        for it in items:
            recalled = round(target_bm.reported_map.get(it.number, 0.0), 2)
            new_reported = max(0.0, round(it.reported_amount - recalled, 2))
            new_report = round(it.report_amount + recalled, 2)
            new_state[it.number] = (it.eat_amount, new_report, new_reported)

        target_bm.reported_map.clear()
        target_bm.report_text = ""
        target_bm.updated_at = ""
        self.eat_repo.save_eat_report_state(region, new_state)
        self.eat_repo.save_bookmaker(target_bm)

    def withdraw_all_bookmakers_reports(self, region: str) -> None:
        """撤回所有上庄的上报数据（对应 `btn撤回全部上报数据_Click`）"""
        bms = self.ensure_bookmakers(region)
        for bm in bms:
            bm.reported_map.clear()
            bm.report_text = ""
            bm.updated_at = ""
            self.eat_repo.save_bookmaker(bm)

        items = self.get_region_risk_items(region)
        new_state = {
            it.number: (it.eat_amount, max(0.0, round(it.total_bet - it.eat_amount, 2)), 0.0)
            for it in items
        }
        self.eat_repo.save_eat_report_state(region, new_state)
