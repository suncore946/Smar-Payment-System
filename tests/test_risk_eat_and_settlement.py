"""
风控吃码上报、开奖对奖算账、Excel 导入导出与 SQLite 备份恢复测试 (test_risk_eat_and_settlement.py)
"""

from __future__ import annotations
from pathlib import Path
import pytest
from src.domain.models import CopyFormat, ParsedBetItem
from src.services.app_controller import ApplicationController
from src.services.risk_eat_service import RiskAndEatService


class TestRiskEatAndSettlement:
    """测试风控计算、二分吃码反推、多上庄报单撤回、开奖结算与数据库持久化"""

    def test_risk_value_formula(self) -> None:
        # 总收单 10000，回水 2% (0.02)，赔率 47，某号押注 200
        # 风险值 = 10000 * 0.98 - 200 * 47 = 9800 - 9400 = +400
        val = RiskAndEatService.calculate_risk_value(10000.0, 200.0, 47.0, 0.02)
        assert val == pytest.approx(400.0)

    def test_submit_delete_and_settle_workflow(self, clean_controller: ApplicationController) -> None:
        region = "新澳门"
        clean_controller.current_region = region
        clean_controller.set_active_client("客户1", region)

        # 1. 录入两笔订单
        items1 = [ParsedBetItem(numbers=[1, 2, 3], per_number_amount=100.0, total_amount=300.0)]
        items2 = [ParsedBetItem(numbers=[1, 8], per_number_amount=200.0, total_amount=400.0)]

        ord1 = clean_controller.submit_bet_items(items1, raw_text="01,02,03各100", region=region)
        ord2 = clean_controller.submit_bet_items(items2, raw_text="01,08各200", region=region)
        assert ord1 is not None and ord2 is not None

        totals = clean_controller.client_repo.get_region_total_bets_by_number(region)
        assert totals[1] == pytest.approx(300.0)
        assert totals[2] == pytest.approx(100.0)
        assert totals[8] == pytest.approx(200.0)

        # 2. 开奖特码 01 号对奖算账
        c_list, grand = clean_controller.settlement_service.settle_region(region, winning_number=1)
        assert grand.total_bet == pytest.approx(700.0)
        assert grand.winning_bet == pytest.approx(300.0)
        # 客户1 默认赔率 47，回水 0 -> 盈亏 = 700 - 300 * 47 = -13400
        assert grand.net_pnl == pytest.approx(700.0 - 300.0 * 47.0)

        # 3. 撤单第 2 笔订单并验证自动扣回押注
        assert ord2.id is not None
        clean_controller.settlement_service.delete_order_and_revert_bets(ord2.id)
        totals_after = clean_controller.client_repo.get_region_total_bets_by_number(region)
        assert totals_after[1] == pytest.approx(100.0)
        assert totals_after[8] == pytest.approx(0.0)

    def test_max_loss_binary_search_and_bookmaker_submit_withdraw(
        self, controller: ApplicationController
    ) -> None:
        region = "新澳门"
        # 测试最大允许亏损二分反推最佳吃码上限
        max_loss = 1500.0
        optimal_cap, updated_items = controller.risk_service.apply_max_loss_eat(region, max_loss)
        assert optimal_cap >= 0.0
        worst_eat_risk = min(it.eat_risk_value for it in updated_items)
        assert worst_eat_risk >= -max_loss - 1e-6

        # 测试格式化复制文本
        copy_str = controller.risk_service.format_copy_text(
            region, data_type="上报", copy_format=CopyFormat.SPACE, increase_percent=0.0
        )
        assert "上报数据明细：" in copy_str

        # 测试提交预备上报给「上庄张」并撤回
        pending_before = sum(it.report_amount for it in updated_items)
        assert pending_before > 0

        bm_rec = controller.risk_service.submit_report_to_bookmaker(region, "上庄张")
        assert "上庄张" in bm_rec.report_text
        after_submit = controller.risk_service.get_region_risk_items(region)
        assert sum(it.report_amount for it in after_submit) == pytest.approx(0.0)
        assert sum(it.reported_amount for it in after_submit) == pytest.approx(pending_before)

        # 撤回上庄张上报
        controller.risk_service.withdraw_bookmaker_report(region, "上庄张")
        after_withdraw = controller.risk_service.get_region_risk_items(region)
        assert sum(it.reported_amount for it in after_withdraw) == pytest.approx(0.0)
        assert sum(it.report_amount for it in after_withdraw) == pytest.approx(pending_before)

    def test_excel_export_and_sqlite_backup(
        self, controller: ApplicationController, tmp_path: Path
    ) -> None:
        # 1. 导出 Excel 报表
        out_xlsx = tmp_path / "export_test.xlsx"
        saved_path = controller.migration_service.export_to_excel(out_xlsx, region="新澳门")
        assert saved_path.exists()
        assert saved_path.stat().st_size > 2000

        # 2. 备份 SQLite 数据库文件
        backup_db = tmp_path / "backup_test.db"
        controller.db_manager.backup_to(backup_db)
        assert backup_db.exists()
        assert backup_db.stat().st_size > 4096
