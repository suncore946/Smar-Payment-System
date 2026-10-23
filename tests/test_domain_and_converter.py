"""
领域模型、中文数字转换器与动态生肖号码属性引擎单元测试
"""

from __future__ import annotations
import pytest
from src.domain.attribute_engine import NumberAttributeEngine
from src.services.chinese_num_converter import ChineseNumberConverter


class TestChineseNumberConverter:
    """测试中文大写/口语数字与混合数字转换器"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("十", 10.0),
            ("十五", 15.0),
            ("二十", 20.0),
            ("二十五", 25.0),
            ("一百", 100.0),
            ("一百零五", 105.0),
            ("四百二", 420.0),
            ("三千五", 3500.0),
            ("二千零三十", 2030.0),
            ("4百20", 420.0),
            ("5十", 50.0),
            ("1千5", 1500.0),
            ("3.5", 3.5),
            ("五块", 5.0),
        ],
    )
    def test_to_num_conversion(self, raw: str, expected: float) -> None:
        val = ChineseNumberConverter.to_num(raw)
        assert val == pytest.approx(expected)

    def test_replace_chinese_amounts_in_text(self) -> None:
        txt = "马各4百20"
        converted = ChineseNumberConverter.normalize_mixed_chinese_amount(txt)
        assert "420" in converted


class TestNumberAttributeEngine:
    """测试 1-49 号码属性引擎与本命年生肖动态推算"""

    def test_horse_year_zodiac_mapping(self) -> None:
        engine = NumberAttributeEngine(base_zodiac="马")
        z_map = engine.get_zodiac_numbers_map()
        # 马年本命年应包含 01, 13, 25, 37, 49 共 5 个号
        assert z_map["马"] == [1, 13, 25, 37, 49]
        assert z_map["蛇"] == [2, 14, 26, 38]
        assert z_map["羊"] == [12, 24, 36, 48]
        # 12 生肖合起来必须完整覆盖 1..49 且不重不漏
        all_nums = sorted(n for nums in z_map.values() for n in nums)
        assert all_nums == list(range(1, 50))

    def test_dynamic_zodiac_year_switch(self) -> None:
        engine = NumberAttributeEngine(base_zodiac="马")
        engine.set_base_zodiac("羊")
        z_map = engine.get_zodiac_numbers_map()
        assert z_map["羊"] == [1, 13, 25, 37, 49]
        assert z_map["马"] == [2, 14, 26, 38]

    def test_wave_and_parity_tags(self) -> None:
        engine = NumberAttributeEngine(base_zodiac="马")
        reds = set(engine.get_numbers_by_tag("红波"))
        blues = set(engine.get_numbers_by_tag("蓝波"))
        greens = set(engine.get_numbers_by_tag("绿波"))
        assert len(reds) + len(blues) + len(greens) == 49
        assert reds.isdisjoint(blues)
        assert reds.isdisjoint(greens)
        assert blues.isdisjoint(greens)

        # 复合条件交集：红波 + 单 = 红单
        inter = engine.resolve_multi_tags(["红波", "单"], intersection=True)
        assert set(inter) == set(engine.get_numbers_by_tag("红单"))

    def test_invert_numbers(self) -> None:
        engine = NumberAttributeEngine(base_zodiac="马")
        selected = [1, 2, 3, 4, 5]
        inverted = engine.invert_numbers(selected)
        assert len(inverted) == 44
        assert set(inverted) == set(range(6, 50))

    def test_custom_attribute_override(self) -> None:
        engine = NumberAttributeEngine(
            base_zodiac="马",
            custom_overrides={"VIP特选": [6, 8, 18, 28, 49]},
        )
        assert engine.get_numbers_by_tag("VIP特选") == [6, 8, 18, 28, 49]
