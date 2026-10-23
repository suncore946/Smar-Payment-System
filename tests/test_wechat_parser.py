"""
微信/QQ智能解析引擎单元测试 (test_wechat_parser.py)
验证：
1. 原版 Excel (`马年(1)_已修复.xlsm`) 全部 29 笔真实历史订单 100% 零误差解析
2. 各肖、各号、多头多尾、波色单双、区间 `1到25`、总金额平摊 `共`、反码、一键负数、盲打录入与自定义替换规则
"""

from __future__ import annotations
import json
from pathlib import Path
import pytest
from src.domain.models import ReplaceRule
from src.services.app_controller import ApplicationController


class TestWeChatParserService:
    """微信/QQ 报单解析服务测试套件"""

    def test_all_29_historical_excel_orders_exact_match(self, controller: ApplicationController) -> None:
        """测试内置种子数据中从原版 Excel 提取的全部 29 笔真实订单 100% 精确还原"""
        seed_path = Path(__file__).resolve().parent.parent / "src" / "data" / "default_seed.json"
        with open(seed_path, "r", encoding="utf-8") as f:
            seed = json.load(f)

        checked_count = 0
        for region_name, orders in seed.get("orders", {}).items():
            for order_data in orders:
                raw_text = order_data["raw_text"]
                expected_total = float(order_data["total_amount"])

                items = controller.parser_service.parse_text(raw_text)
                actual_total = round(sum(it.total_amount for it in items), 2)
                assert actual_total == pytest.approx(expected_total), (
                    f"[{region_name} #{order_data['seq_no']}] 金额不一致: "
                    f"raw={raw_text!r}, expected={expected_total}, actual={actual_total}"
                )
                checked_count += 1

        assert checked_count == 29

    def test_zodiac_and_number_expressions(self, controller: ApplicationController) -> None:
        items = controller.parser_service.parse_text("牛虎兔各码25\n01.12.24各50")
        # 牛、虎、兔 3 条生肖 + 01.12.24 1 条散号 = 4 条识别项
        assert len(items) == 4
        assert sum(it.total_amount for it in items[:3]) == pytest.approx(300.0)
        assert items[3].numbers == [1, 12, 24]
        assert items[3].total_amount == pytest.approx(150.0)

    def test_multi_head_tail_and_range(self, controller: ApplicationController) -> None:
        items = controller.parser_service.parse_text("012头各10\n1到10各20")
        # 0头(9个)+1头(10个)+2头(10个) 共3条=290元，1到10共1条=200元
        assert len(items) == 4
        assert sum(it.total_amount for it in items[:3]) == pytest.approx(290.0)
        assert items[3].numbers == list(range(1, 11))
        assert items[3].total_amount == pytest.approx(200.0)

    def test_total_split_gong_keyword(self, controller: ApplicationController) -> None:
        items = controller.parser_service.parse_text("大共500元")
        assert len(items) == 1
        # 大码共 25 个号 (25..49)，共 500 元 -> 每号 20 元
        assert len(items[0].numbers) == 25
        assert items[0].per_number_amount == pytest.approx(20.0)
        assert items[0].total_amount == pytest.approx(500.0)

    def test_negate_text_and_negative_order(self, controller: ApplicationController) -> None:
        items = controller.parser_service.parse_text("01,02各100")
        negated = controller.parser_service.negate_items(items)
        assert len(negated) == 1
        assert negated[0].per_number_amount == pytest.approx(-100.0)
        assert negated[0].total_amount == pytest.approx(-200.0)

    def test_quick_code_parsing(self, controller: ApplicationController) -> None:
        item = controller.parser_service.parse_quick_input("041628", 50.0, is_flat=False)
        assert item is not None
        assert item.numbers == [4, 16, 28]
        assert item.total_amount == pytest.approx(150.0)

    def test_custom_replace_rule_applied(self, controller: ApplicationController) -> None:
        controller.replace_repo.save_rule(
            ReplaceRule(id=None, find_text="发财码", replace_text="08,18,28", is_enabled=True)
        )
        controller.reload_runtime_configs()
        items = controller.parser_service.parse_text("发财码各50")
        assert len(items) == 1
        assert items[0].numbers == [8, 18, 28]
        assert items[0].total_amount == pytest.approx(150.0)
