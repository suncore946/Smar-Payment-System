"""
订单入库、撤单扣减与开奖对奖算账服务 (SettlementService)
完整复刻并增强原 Excel VBA 中的 `微信提取_添加模块`、`明细模块`（双击删除订单）、
`模块1.ClearCs`（清空数据）及 `分人统计_对奖和算账.frm`（开奖特码对奖与算账）核心逻辑。
"""

from __future__ import annotations
from datetime import datetime
import re
from typing import Dict, List, Optional, Tuple
from src.database.repositories import (
    ClientRepository,
    EatReportRepository,
    OrderRepository,
    RegionRepository,
)
from src.domain.models import (
    ClientSettlementItem,
    OrderRecord,
    ParsedBetItem,
)
from .wechat_parser_service import WeChatParserService


class SettlementService:
    """面向对象订单管理与开奖结算服务"""

    def __init__(
        self,
        region_repo: RegionRepository,
        client_repo: ClientRepository,
        order_repo: OrderRepository,
        eat_repo: EatReportRepository,
    ) -> None:
        self.region_repo = region_repo
        self.client_repo = client_repo
        self.order_repo = order_repo
        self.eat_repo = eat_repo

    def submit_parsed_order(
        self,
        region: str,
        client_name: str,
        raw_text: str,
        items: List[ParsedBetItem],
    ) -> Optional[OrderRecord]:
        """
        将识别确认后的多条 `ParsedBetItem` 合并生成一笔订单入库，并累加对应客户 1-49 号统计金额
        """
        valid_items = [it for it in items if it.validate()]
        if not valid_items:
            return None

        delta_bets: Dict[int, float] = {}
        canonical_lines: List[str] = []
        order_total = 0.0

        for it in valid_items:
            canonical_lines.append(it.canonical_expression)
            order_total = round(order_total + it.total_amount, 2)
            for num in it.numbers:
                if 1 <= num <= 49:
                    delta_bets[num] = round(delta_bets.get(num, 0.0) + it.per_number_amount, 2)

        parsed_content = "\n".join(canonical_lines)
        clean_raw = raw_text.strip() if raw_text and raw_text.strip() else parsed_content

        # 更新客户 1-49 号押注金额
        self.client_repo.add_client_bets(region, client_name, delta_bets)

        # 创建订单记录
        order = OrderRecord(
            id=None,
            seq_no=0,
            region=region,
            client_name=client_name,
            raw_text=clean_raw,
            parsed_content=parsed_content,
            total_amount=order_total,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.order_repo.add_order(order)

        # 若当前盘口已设置开奖号码，自动同步计算该笔新订单的对奖盈亏
        reg_cfg = self.region_repo.get_region(region)
        if reg_cfg and 1 <= reg_cfg.last_winning_number <= 49:
            self._compute_single_order_settlement(order, reg_cfg.last_winning_number)
            self.order_repo.update_order_settlement(order)

        return order

    def delete_order_and_revert_bets(self, order_id: int) -> bool:
        """
        删除指定订单并从对应客户的 1-49 号汇总数据中扣回该笔押注（对应原 `明细删除`）
        """
        order = self.order_repo.get_order_by_id(order_id)
        if not order:
            return False

        num_amounts = WeChatParserService.parse_canonical_order_content(order.parsed_content)
        revert_deltas = {num: -amt for num, amt in num_amounts.items()}
        self.client_repo.add_client_bets(order.region, order.client_name, revert_deltas)
        self.order_repo.delete_order(order_id)
        return True

    def rebuild_region_client_bets_from_orders(self, region: str) -> None:
        """根据订单明细表重新校验并同步计算所有客户的 1-49 号押注总额"""
        clients = {c.name: c for c in self.client_repo.list_clients(region)}
        for c in clients.values():
            c.number_bets = {i: 0.0 for i in range(1, 50)}

        orders = self.order_repo.list_orders(region)
        for o in orders:
            if o.client_name not in clients:
                clients[o.client_name] = self.client_repo.get_client(region, o.client_name)
            c_obj = clients.get(o.client_name)
            if not c_obj:
                continue
            num_map = WeChatParserService.parse_canonical_order_content(o.parsed_content)
            for num, amt in num_map.items():
                if 1 <= num <= 49:
                    c_obj.number_bets[num] = round(c_obj.number_bets.get(num, 0.0) + amt, 2)

        for c in clients.values():
            if c:
                self.client_repo.save_client(c)

    def _get_client_odds_and_rebate(self, region: str, client_name: str) -> Tuple[float, float]:
        client = self.client_repo.get_client(region, client_name)
        reg = self.region_repo.get_region(region)
        default_odds = reg.global_odds if reg else 47.0
        default_rebate = reg.global_rebate if reg else 0.0

        if client:
            odds = client.odds if client.odds > 0 else default_odds
            rebate = client.rebate
            return odds, rebate
        return default_odds, default_rebate

    def _compute_single_order_settlement(self, order: OrderRecord, winning_number: int) -> None:
        num_map = WeChatParserService.parse_canonical_order_content(order.parsed_content)
        win_amt = round(num_map.get(winning_number, 0.0), 2)
        odds, rebate = self._get_client_odds_and_rebate(order.region, order.client_name)

        pnl_no_rebate = round(order.total_amount - odds * win_amt, 2)
        rebate_amt = round(-order.total_amount * rebate, 2)
        net_pnl = round(pnl_no_rebate + rebate_amt, 2)

        order.winning_amount = win_amt
        order.pnl_no_rebate = pnl_no_rebate
        order.rebate_amount = rebate_amt
        order.net_pnl = net_pnl

    def settle_region(
        self,
        region: str,
        winning_number: Optional[int],
    ) -> Tuple[List[ClientSettlementItem], ClientSettlementItem]:
        """
        对指定盘口执行开奖对奖算账（对应原 `分人统计_对奖和算账.frm` -> `确定_Click`）：
        - 若 `winning_number` 为 1~49，计算每笔订单与每位客户的中码金额、盈亏(不包回水)、回水、总盈亏(含回水)
        - 若 `winning_number` 为 None 或 0，清除对奖中码信息，仅汇总下单金额
        返回 `(per_client_list, grand_total_item)`
        """
        reg_cfg = self.region_repo.get_region(region)
        orders = self.order_repo.list_orders(region)

        has_win = winning_number is not None and 1 <= int(winning_number) <= 49
        win_num = int(winning_number) if has_win else 0

        if reg_cfg:
            reg_cfg.last_winning_number = win_num
            self.region_repo.save_region(reg_cfg)

        if not has_win:
            self.order_repo.reset_region_settlement(region)
            orders = self.order_repo.list_orders(region)

        client_stats: Dict[str, ClientSettlementItem] = {}

        for order in orders:
            if has_win:
                self._compute_single_order_settlement(order, win_num)
                self.order_repo.update_order_settlement(order)
            else:
                order.winning_amount = 0.0
                order.pnl_no_rebate = 0.0
                order.rebate_amount = 0.0
                order.net_pnl = 0.0

            c_name = order.client_name
            if c_name not in client_stats:
                odds, rebate = self._get_client_odds_and_rebate(region, c_name)
                client_stats[c_name] = ClientSettlementItem(
                    client_name=c_name,
                    odds=odds,
                    rebate=rebate,
                    total_bet=0.0,
                    winning_bet=0.0,
                    pnl_no_rebate=0.0,
                    rebate_amount=0.0,
                    net_pnl=0.0,
                    order_count=0,
                )
            st = client_stats[c_name]
            st.total_bet = round(st.total_bet + order.total_amount, 2)
            st.winning_bet = round(st.winning_bet + order.winning_amount, 2)
            st.order_count += 1

        results: List[ClientSettlementItem] = []
        tot_bet = 0.0
        tot_win = 0.0
        tot_pnl_no_reb = 0.0
        tot_reb = 0.0
        tot_net = 0.0
        tot_cnt = 0

        for st in client_stats.values():
            if has_win:
                st.pnl_no_rebate = round(st.total_bet - st.odds * st.winning_bet, 2)
                st.rebate_amount = round(-st.total_bet * st.rebate, 2)
                st.net_pnl = round(st.pnl_no_rebate + st.rebate_amount, 2)
            results.append(st)
            tot_bet = round(tot_bet + st.total_bet, 2)
            tot_win = round(tot_win + st.winning_bet, 2)
            tot_pnl_no_reb = round(tot_pnl_no_reb + st.pnl_no_rebate, 2)
            tot_reb = round(tot_reb + st.rebate_amount, 2)
            tot_net = round(tot_net + st.net_pnl, 2)
            tot_cnt += st.order_count

        grand_total = ClientSettlementItem(
            client_name="合计：",
            odds=0.0,
            rebate=0.0,
            total_bet=tot_bet,
            winning_bet=tot_win,
            pnl_no_rebate=tot_pnl_no_reb,
            rebate_amount=tot_reb,
            net_pnl=tot_net,
            order_count=tot_cnt,
        )
        return results, grand_total

    def clear_region_all_data(self, region: str) -> None:
        """一键清空当前盘口所有订单、分人统计押注与吃码上报状态（对应原 `ClearCs`）"""
        self.order_repo.clear_region_orders(region)
        self.client_repo.clear_region_bets(region)
        self.eat_repo.clear_region_eat_state(region)
        reg = self.region_repo.get_region(region)
        if reg:
            reg.last_winning_number = 0
            self.region_repo.save_region(reg)

    @staticmethod
    def highlight_winning_number_html(parsed_content: str, winning_number: int) -> str:
        """将押注内容中的中奖号码高亮为醒目红色加粗 HTML"""
        if not parsed_content:
            return ""
        text = parsed_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if not winning_number or winning_number < 1 or winning_number > 49:
            return text.replace("\n", "<br>")

        target_2d = f"{winning_number:02d}"
        target_1d = str(winning_number)
        pattern = re.compile(rf"(^|[,，\n])({target_2d}|{target_1d})(?=[,，各])")

        def _repl(m: re.Match) -> str:
            return f'{m.group(1)}<span style="color:#dc2626;font-weight:bold;font-size:14px;background:#fee2e2;padding:0 2px;border-radius:3px;">{m.group(2)}</span>'

        highlighted = pattern.sub(_repl, text)
        return highlighted.replace("\n", "<br>")
