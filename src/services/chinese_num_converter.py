"""
中文金额与阿拉伯数字转换器 (ChineseNumberConverter)
完整复刻并增强原 VBA 模块 `中文小写转数字.bas` 与 `中文简写补全` 逻辑
"""

from __future__ import annotations
import re


class ChineseNumberConverter:
    """
    面向对象中文小写/大写/混合金额转阿拉伯数字工具类
    支持：
    - 纯阿拉伯数字/小数/负数: "100", "12.5", "-50"
    - 纯中文数字: "五" -> 5, "十五" -> 15, "二十五" -> 25, "三百" -> 300, "两千五百" -> 2500
    - 简写中文金额: "四百二" -> 420, "三千五" -> 3500, "一万二" -> 12000
    - 混合数字: "4百2" -> 420, "4百20" -> 420, "3百" -> 300
    """

    CN_DIGITS = {
        "零": 0, "〇": 0, "0": 0,
        "一": 1, "壹": 1, "1": 1,
        "二": 2, "贰": 2, "两": 2, "俩": 2, "2": 2,
        "三": 3, "叁": 3, "≡": 3, "3": 3,
        "四": 4, "肆": 4, "4": 4,
        "五": 5, "伍": 5, "5": 5,
        "六": 6, "陆": 6, "6": 6,
        "七": 7, "柒": 7, "7": 7,
        "八": 8, "捌": 8, "8": 8,
        "九": 9, "玖": 9, "9": 9,
    }

    CN_UNITS = {
        "十": 10, "拾": 10,
        "百": 100, "佰": 100,
        "千": 1000, "仟": 1000,
        "万": 10000,
        "亿": 100000000,
    }

    NEXT_UNIT_MAP = {
        "万": 1000,
        "千": 100,
        "仟": 100,
        "百": 10,
        "佰": 10,
    }

    @classmethod
    def normalize_mixed_chinese_amount(cls, text: str) -> str:
        """
        将如 '4百20'、'4百2'、'3十5' 等阿拉伯与中文单位混合字符串规范化
        """
        if not text:
            return text
        digit_to_cn = {
            "0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
            "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
        }

        def _repl(match: re.Match) -> str:
            s = match.group(0)
            # handle e.g. 4百20 -> 420
            m_tail2 = re.fullmatch(r"([1-9])([百佰千仟万])(\d{2,})", s)
            if m_tail2:
                d1 = int(m_tail2.group(1))
                unit = cls.CN_UNITS[m_tail2.group(2)]
                tail = int(m_tail2.group(3))
                return str(d1 * unit + tail)
            out = []
            for ch in s:
                out.append(digit_to_cn.get(ch, ch))
            return "".join(out)

        return re.sub(r"[1-9][十拾百佰千仟万][0-9十拾百佰千仟一二三四五六七八九零〇]*", _repl, text)

    @classmethod
    def to_num(cls, mystr: str | int | float) -> float:
        """将数字或中文金额字符串转换为浮点数"""
        if isinstance(mystr, (int, float)):
            return float(mystr)
        if not mystr:
            return 0.0

        s = str(mystr).strip()
        if not s:
            return 0.0

        # 去除常见货币/单位后缀
        s = re.sub(r"[元斤米咪闷皮块号个]$", "", s).strip()
        if not s:
            return 0.0

        sign = 1.0
        if s.startswith("-"):
            sign = -1.0
            s = s[1:].strip()
        elif s.startswith("+"):
            s = s[1:].strip()

        # 直接尝试标准浮点数
        try:
            return sign * float(s)
        except ValueError:
            pass

        # 预处理如 "4百20" -> 420
        m_mix = re.fullmatch(r"([1-9])([百佰千仟万])(\d{2,})", s)
        if m_mix:
            val = int(m_mix.group(1)) * cls.CN_UNITS[m_mix.group(2)] + int(m_mix.group(3))
            return sign * float(val)

        # 检查简写中文，如 "四百二"、"4百2"、"三千五"（末尾是数字且前一位是百/千/万，且中间没有“零”）
        last_unit_char = ""
        for ch in reversed(s[:-1]):
            if ch in cls.CN_UNITS:
                last_unit_char = ch
                break
            if ch in ("零", "〇"):
                last_unit_char = ""
                break

        trailing_multiplier = 1
        if s[-1] in cls.CN_DIGITS and s[-1] not in ("零", "〇", "0") and last_unit_char in cls.NEXT_UNIT_MAP:
            trailing_multiplier = cls.NEXT_UNIT_MAP[last_unit_char]

        total = 0
        section = 0
        current_digit = 0
        has_any = False

        for idx, ch in enumerate(s):
            if ch in cls.CN_DIGITS:
                current_digit = cls.CN_DIGITS[ch]
                has_any = True
                if idx == len(s) - 1:
                    section += current_digit * trailing_multiplier
                    current_digit = 0
            elif ch in cls.CN_UNITS:
                has_any = True
                unit_val = cls.CN_UNITS[ch]
                if unit_val >= 10000:
                    section += current_digit
                    if section == 0:
                        section = 1
                    total += section * unit_val
                    section = 0
                else:
                    if current_digit == 0 and (idx == 0 or s[idx - 1] in cls.CN_UNITS or s[idx - 1] in ("零", "〇")):
                        current_digit = 1
                    section += current_digit * unit_val
                current_digit = 0

        total += section + current_digit
        if not has_any:
            # 退火提取数字
            m_num = re.search(r"-?\d+(?:\.\d+)?", str(mystr))
            if m_num:
                return float(m_num.group(0))
            return 0.0
        return sign * float(total)
