"""
号码属性与生肖波色映射引擎 (Number Attribute Engine)
完整复刻并增强原 Excel VBA 中的 GetCAType()、生肖字典()、取反码() 及选号助手交并集逻辑，
支持本命年生肖动态切换与用户自定义属性映射覆盖。
"""

from __future__ import annotations
from typing import Dict, Iterable, List, Optional, Set


class NumberAttributeEngine:
    """
    面向对象号码属性映射与计算引擎（1-49号）
    支持：
    1. 十二生肖动态年份计算（默认“马”年：马=01,13,25,37,49；蛇=02,14,26,38...）
    2. 波色（红波、蓝波/兰波、绿波）及波色单双大小组合
    3. 单双、大小、合单/合双/合大/合小、1-13合
    4. 0-4头（含头单/头双）、0-9尾（含大尾/小尾）、1-12岁
    5. 五行（金木水火土）、家禽/野兽、天地吉凶阴阳男女朝夕肖、偏旁/笔画肖
    6. 特殊位置码（内外围、前后、左右、楼上楼下、风雨、深浅、拼搏、高低、长短、黑白、冷热、爱恨、顺逆、天地码、反数）
    7. 号码反码与生肖反码计算
    8. 用户自定义属性字典覆盖
    """

    ZODIAC_SEQUENCE: List[str] = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
    ZODIAC_ORDER: List[str] = ZODIAC_SEQUENCE

    RED_WAVE_NUMS: List[int] = [1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46]
    BLUE_WAVE_NUMS: List[int] = [3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48]
    GREEN_WAVE_NUMS: List[int] = [5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49]

    ZODIAC_GROUPS: Dict[str, List[str]] = {
        "家禽": ["牛", "马", "羊", "鸡", "狗", "猪"],
        "家肖": ["牛", "马", "羊", "鸡", "狗", "猪"],
        "家畜": ["牛", "马", "羊", "鸡", "狗", "猪"],
        "家": ["牛", "马", "羊", "鸡", "狗", "猪"],
        "野兽": ["鼠", "虎", "兔", "龙", "蛇", "猴"],
        "野肖": ["鼠", "虎", "兔", "龙", "蛇", "猴"],
        "野": ["鼠", "虎", "兔", "龙", "蛇", "猴"],
        "马边": ["马", "羊", "猴", "鸡", "狗", "猪"],
        "鼠边": ["鼠", "牛", "虎", "兔", "龙", "蛇"],
        "单笔画肖": ["鼠", "猪", "鸡", "马", "蛇", "龙"],
        "双笔画肖": ["兔", "虎", "牛", "狗", "猴", "羊"],
        "吉肖": ["兔", "鸡", "羊", "马", "蛇", "龙"],
        "凶肖": ["虎", "牛", "鼠", "猪", "狗", "猴"],
        "天肖": ["兔", "牛", "猪", "猴", "马", "龙"],
        "地肖": ["虎", "鼠", "狗", "鸡", "羊", "蛇"],
        "阴肖": ["鼠", "猪", "狗", "马", "蛇", "龙"],
        "阳肖": ["兔", "虎", "牛", "鸡", "猴", "羊"],
        "男肖": ["虎", "牛", "鼠", "狗", "猴", "马", "龙"],
        "女肖": ["兔", "猪", "鸡", "羊", "蛇"],
        "有偏旁肖": ["猪", "狗", "鸡", "猴", "蛇"],
        "无偏旁肖": ["兔", "虎", "牛", "鼠", "羊", "马", "龙"],
        "朝肖": ["兔", "猴", "羊", "马", "蛇", "龙"],
        "夕肖": ["虎", "牛", "鼠", "猪", "狗", "鸡"],
    }

    def __init__(self, base_zodiac: str = "马", custom_overrides: Optional[Dict[str, str]] = None) -> None:
        self._base_zodiac = base_zodiac if base_zodiac in self.ZODIAC_SEQUENCE else "马"
        self._custom_overrides: Dict[str, str] = dict(custom_overrides) if custom_overrides else {}
        self._zodiac_to_nums: Dict[str, List[int]] = {}
        self._num_to_zodiac: Dict[int, str] = {}
        self._ca_dict: Dict[str, str] = {}
        self._rebuild()

    @property
    def base_zodiac(self) -> str:
        return self._base_zodiac

    def set_base_zodiac(self, base_zodiac: str) -> None:
        if base_zodiac in self.ZODIAC_SEQUENCE:
            self._base_zodiac = base_zodiac
            self._rebuild()

    def set_custom_overrides(self, overrides: Dict[str, str]) -> None:
        self._custom_overrides = dict(overrides)
        self._rebuild()

    def get_custom_overrides(self) -> Dict[str, str]:
        return dict(self._custom_overrides)

    @staticmethod
    def format_nums(nums: Iterable[int]) -> str:
        return ",".join(f"{n:02d}" for n in nums)

    @staticmethod
    def parse_nums_str(nums_str: str | Iterable[int]) -> List[int]:
        if not isinstance(nums_str, str):
            return [int(x) for x in nums_str if 1 <= int(x) <= 49]
        result: List[int] = []
        for part in nums_str.replace("，", ",").split(","):
            part = part.strip()
            if part.isdigit():
                val = int(part)
                if 1 <= val <= 49 and val not in result:
                    result.append(val)
        return result

    def _rebuild(self) -> None:
        """根据当前本命年生肖及自定义覆盖重建全量属性映射字典"""
        base_idx = self.ZODIAC_SEQUENCE.index(self._base_zodiac)
        self._zodiac_to_nums.clear()
        self._num_to_zodiac.clear()

        # 1. 计算 12 生肖对应的号码（例如马年：马=1,13,25,37,49，蛇=2,14,26,38，龙=3,15,27,39...）
        for offset in range(12):
            # 往回退 offset 个生肖对应年龄 1 + offset
            z_idx = (base_idx - offset) % 12
            zodiac_name = self.ZODIAC_SEQUENCE[z_idx]
            start_num = offset + 1
            nums = [n for n in range(start_num, 50, 12)]
            self._zodiac_to_nums[zodiac_name] = nums
            for n in nums:
                self._num_to_zodiac[n] = zodiac_name

        # 如果用户在 custom_overrides 中自定义了某个单生肖的号码，优先应用
        for z_name in self.ZODIAC_SEQUENCE:
            if z_name in self._custom_overrides:
                parsed = self.parse_nums_str(self._custom_overrides[z_name])
                if parsed:
                    self._zodiac_to_nums[z_name] = parsed
                    for n in parsed:
                        self._num_to_zodiac[n] = z_name

        ca: Dict[str, str] = {}

        # 2. 1-49 单号映射
        for i in range(1, 50):
            s2 = f"{i:02d}"
            ca[s2] = s2
            ca[str(i)] = s2

        # 3. 12生肖与别名、繁体字
        zodiac_aliases = {
            "老鼠": "鼠",
            "老虎": "虎",
            "老蛇": "蛇",
            "馬": "马",
            "龍": "龙",
            "雞": "鸡",
            "豬": "猪",
        }
        for z_name in self.ZODIAC_SEQUENCE:
            ca[z_name] = self.format_nums(self._zodiac_to_nums[z_name])
        for alias, target in zodiac_aliases.items():
            ca[alias] = ca[target]

        # 4. 生肖组合（家禽、野兽、天地吉凶阴阳等）
        for grp_name, z_list in self.ZODIAC_GROUPS.items():
            combined: List[int] = []
            for z in z_list:
                combined.extend(self._zodiac_to_nums[z])
            ca[grp_name] = self.format_nums(combined)

        # 5. 单双、大小、大单/小单/大双/小双
        ca["小单"] = "01,03,05,07,09,11,13,15,17,19,21,23"
        ca["大单"] = "25,27,29,31,33,35,37,39,41,43,45,47,49"
        ca["小双"] = "02,04,06,08,10,12,14,16,18,20,22,24"
        ca["大双"] = "26,28,30,32,34,36,38,40,42,44,46,48"

        odd_str = "01,03,05,07,09,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47,49"
        for k in ("单", "单数", "单号"):
            ca[k] = odd_str

        even_str = "02,04,06,08,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48"
        for k in ("双", "双数", "双号"):
            ca[k] = even_str

        big_str = "25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49"
        for k in ("大", "大数", "大号"):
            ca[k] = big_str

        small_str = "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24"
        for k in ("小", "小数", "小号"):
            ca[k] = small_str

        # 6. 红波、蓝波(兰波)、绿波及其单双大小细分
        red_str = self.format_nums(self.RED_WAVE_NUMS)
        for k in ("红波", "红"):
            ca[k] = red_str
        ca["红小"] = "01,02,07,08,12,13,18,19,23,24"
        ca["红大"] = "29,30,34,35,40,45,46"
        for k in ("红双", "红波双", "红波双数"):
            ca[k] = "02,08,12,18,24,30,34,40,46"
        for k in ("红单", "红波单", "红波单数"):
            ca[k] = "01,07,13,19,23,29,35,45"

        blue_str = self.format_nums(self.BLUE_WAVE_NUMS)
        for k in ("蓝波", "蓝", "兰波", "兰"):
            ca[k] = blue_str
        ca["蓝小"] = "03,04,09,10,14,15,20"
        ca["蓝大"] = "25,26,31,36,37,41,42,47,48"
        for k in ("蓝双", "蓝波双", "蓝波双数", "兰双", "兰波双", "兰波双数"):
            ca[k] = "04,10,14,20,26,36,42,48"
        for k in ("蓝单", "蓝波单", "蓝波单数", "兰单", "兰波单", "兰波单数"):
            ca[k] = "03,09,15,25,31,37,41,47"

        green_str = self.format_nums(self.GREEN_WAVE_NUMS)
        for k in ("绿波", "绿"):
            ca[k] = green_str
        ca["绿小"] = "05,06,11,16,17,21,22"
        ca["绿大"] = "27,28,32,33,38,39,43,44,49"
        for k in ("绿双", "绿波双", "绿波双数"):
            ca[k] = "06,16,22,28,32,38,44"
        for k in ("绿单", "绿波单", "绿波单数"):
            ca[k] = "05,11,17,21,27,33,39,43,49"

        # 7. 尾数（0尾-9尾、零尾-九尾、大尾、小尾）
        cn_digits = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
        for d in range(10):
            tail_nums = [n for n in range(1, 50) if n % 10 == d]
            t_str = self.format_nums(tail_nums)
            ca[f"{d}尾"] = t_str
            ca[f"{cn_digits[d]}尾"] = t_str
        ca["小尾"] = "10,20,30,40,01,11,21,31,41,02,12,22,32,42,03,13,23,33,43,04,14,24,34,44"
        ca["大尾"] = "05,15,25,35,45,06,16,26,36,46,07,17,27,37,47,08,18,28,38,48,09,19,29,39,49"

        # 8. 合数（合单、合双、合大、合小、1合-13合）
        he_odd = "01,03,05,07,09,10,12,14,16,18,21,23,25,27,29,30,32,34,36,38,41,43,45,47,49"
        for k in ("合单", "合数单", "合数单数"):
            ca[k] = he_odd
        he_even = "02,04,06,08,11,13,15,17,19,20,22,24,26,28,31,33,35,37,39,40,42,44,46,48"
        for k in ("合双", "合数双", "合数双数"):
            ca[k] = he_even
        ca["合小"] = "01,02,03,04,05,06,10,11,12,13,14,15,20,21,22,23,24,30,31,32,33,40,41,42"
        ca["合大"] = "07,08,09,16,17,18,19,25,26,27,28,29,34,35,36,37,38,39,43,44,45,46,47,48,49"

        he_cn = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三"]
        for s in range(1, 14):
            s_nums = [n for n in range(1, 50) if (n // 10 + n % 10) == s]
            s_str = self.format_nums(s_nums)
            ca[f"{s}合"] = s_str
            ca[f"{he_cn[s]}合"] = s_str

        # 9. 头数（0头-4头，含单双）
        ca["0头"] = "01,02,03,04,05,06,07,08,09"
        ca["0头双"] = ca["0头双数"] = "02,04,06,08"
        ca["0头单"] = ca["0头单数"] = "01,03,05,07,09"
        ca["1头"] = "10,11,12,13,14,15,16,17,18,19"
        ca["1头双"] = ca["1头双数"] = "10,12,14,16,18"
        ca["1头单"] = ca["1头单数"] = "11,13,15,17,19"
        ca["2头"] = "20,21,22,23,24,25,26,27,28,29"
        ca["2头双"] = ca["2头双数"] = "20,22,24,26,28"
        ca["2头单"] = ca["2头单数"] = "21,23,25,27,29"
        ca["3头"] = "30,31,32,33,34,35,36,37,38,39"
        ca["3头双"] = ca["3头双数"] = "30,32,34,36,38"
        ca["3头单"] = "31,33,35,37,39"
        ca["3头单数"] = "31,33,35,37,39"
        ca["4头"] = "40,41,42,43,44,45,46,47,48,49"
        ca["4头双"] = ca["4头双数"] = "40,42,44,46,48"
        ca["4头单"] = ca["4头单数"] = "41,43,45,47,49"

        # 10. 五行（金木水火土）
        ca["金"] = "03,04,11,12,25,26,33,34,41,42"
        ca["木"] = "07,08,15,16,23,24,37,38,45,46"
        ca["水"] = "13,14,21,22,29,30,43,44"
        ca["火"] = "01,02,09,10,17,18,31,32,39,40,47,48"
        ca["土"] = "05,06,19,20,27,28,35,36,49"

        # 11. 岁数（1岁-12岁，01岁-09岁）
        for age in range(1, 13):
            age_nums = [n for n in range(age, 50, 12)]
            age_str = self.format_nums(age_nums)
            ca[f"{age}岁"] = age_str
            if age < 10:
                ca[f"0{age}岁"] = age_str

        # 12. 特殊方位/属性码
        ca["反数"] = "12,13,14,21,23,24,31,32,34,41,42,43"
        ca["内围码"] = "09,10,11,12,13,16,17,18,19,20,23,24,25,26,27,30,31,32,33,34,37,38,39,40,41"
        ca["外围码"] = "01,02,03,04,05,06,07,08,14,15,21,22,28,29,35,36,42,43,44,45,46,47,48,49"
        ca["前码"] = "01,02,03,04,05,06,07,08,17,18,19,20,21,22,23,24,33,34,35,36,37,38,39,40"
        ca["后码"] = "09,10,11,12,13,14,15,16,25,26,27,28,29,30,31,32,41,42,43,44,45,46,47,48,49"
        ca["左边码"] = "01,02,03,04,08,09,10,11,15,16,17,18,22,23,24,29,30,31,36,37,38,43,44,45"
        ca["右边码"] = "05,06,07,12,13,14,19,20,21,25,26,27,28,32,33,34,35,39,40,41,42,46,47,48,49"
        ca["楼上码"] = "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,25,26,27,28"
        ca["楼下码"] = "22,23,24,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49"
        ca["风码"] = "03,04,06,08,11,13,14,15,17,19,23,24,26,27,31,33,35,36,37,39,42,44,46,47"
        ca["雨码"] = "01,02,05,07,09,10,12,16,18,20,21,22,25,28,29,30,32,34,38,40,41,43,45,48,49"
        ca["深码"] = "01,02,03,07,08,09,13,14,15,19,20,21,25,26,27,31,32,33,37,38,39,43,44,45,49"
        ca["浅码"] = "04,05,06,10,11,12,16,17,18,22,23,24,28,29,30,34,35,36,40,41,42,46,47,48"
        ca["拼码"] = "04,05,06,12,13,14,15,16,21,22,23,24,25,26,27,28,29,34,35,36,37,38,44,45,46"
        ca["搏码"] = "01,02,03,07,08,09,10,11,17,18,19,20,30,31,32,33,39,40,41,42,43,47,48,49"
        ca["高码"] = "01,04,07,08,09,10,12,17,18,19,25,26,27,28,29,30,34,35,36,37,39,44,45,47,48"
        ca["低码"] = "02,03,05,06,11,13,14,15,16,20,21,22,23,24,31,32,33,38,40,41,42,43,46,49"
        ca["长码"] = "01,05,06,07,08,09,13,14,15,16,17,21,22,23,24,25,30,31,32,38,39,40,46,47,48"
        ca["短码"] = "02,03,04,10,11,12,18,19,20,26,27,28,29,33,34,35,36,37,41,42,43,44,45,49"
        ca["黑码"] = "01,02,05,06,09,10,13,14,17,18,21,22,25,26,29,30,33,34,37,38,41,42,45,46,49"
        ca["白码"] = "03,04,07,08,11,12,15,16,19,20,23,24,27,28,31,32,35,36,39,40,43,44,47,48"
        ca["冷码"] = "01,02,04,05,10,11,12,13,19,20,21,22,28,29,30,31,37,38,39,40,45,46,48,49"
        ca["热码"] = "03,06,07,08,09,14,15,16,17,18,23,24,25,26,27,32,33,34,35,36,41,42,43,44,47"
        ca["爱码"] = "01,05,06,07,08,09,10,13,14,15,16,17,18,19,21,25,26,27,28,30,38,39,46,47,48"
        ca["恨码"] = "02,03,04,11,12,20,22,23,24,29,31,32,33,34,35,36,37,40,41,42,43,44,45,49"
        ca["顺码"] = "01,03,05,08,09,14,16,17,20,22,23,24,25,26,27,28,30,33,34,36,41,42,45,47,49"
        ca["逆码"] = "02,04,06,07,10,11,12,13,15,18,19,21,29,31,32,35,37,38,39,40,43,44,46,48"
        ca["天码"] = "01,04,07,09,10,11,14,17,19,20,21,24,27,29,30,31,34,37,39,40,41,44,47,49"
        ca["地码"] = "02,03,05,06,08,12,13,15,16,18,22,23,25,26,28,32,33,35,36,38,42,43,45,46,48"

        # 13. 应用用户的其它自定义覆盖
        for k, v in self._custom_overrides.items():
            parsed = self.parse_nums_str(v)
            if parsed:
                ca[k] = self.format_nums(parsed)

        self._ca_dict = ca

    def get_ca_dict(self) -> Dict[str, str]:
        """获取完整的属性->号码字符串字典（对应原 GetCAType）"""
        return dict(self._ca_dict)

    def get_numbers_by_tag(self, tag: str) -> List[int]:
        """根据属性名称（如'兔'、'红波'、'大单'、'3尾'）返回对应的整数号码列表"""
        val = self._ca_dict.get(tag, "")
        if not val:
            return []
        return self.parse_nums_str(val)

    def get_numbers_str_by_tag(self, tag: str) -> str:
        """根据属性名称返回 '04,16,28,40' 形式的字符串"""
        return self._ca_dict.get(tag, "")

    def get_zodiac_of_number(self, number: int) -> str:
        """返回号码(1-49)所属生肖"""
        return self._num_to_zodiac.get(number, "")

    def get_zodiac_numbers_map(self) -> Dict[str, List[int]]:
        """返回12生肖 -> 号码列表映射"""
        return {z: list(self._zodiac_to_nums[z]) for z in self.ZODIAC_SEQUENCE}

    def get_display_zodiac_rows(self) -> List[tuple[str, List[int]]]:
        """
        返回主面板 12 行展示顺序（与原 Excel 一致：
        第1行是本命年生肖 1,13,25,37,49，第2行是 2,14,26,38 ... 第12行是 12,24,36,48）
        """
        rows: List[tuple[str, List[int]]] = []
        for start_num in range(1, 13):
            z = self.get_zodiac_of_number(start_num)
            nums = [n for n in range(start_num, 50, 12)]
            rows.append((z, nums))
        return rows

    def get_wave_color(self, number: int) -> str:
        """返回号码波色: 'red', 'blue', 或 'green'"""
        if number in self.RED_WAVE_NUMS:
            return "red"
        if number in self.BLUE_WAVE_NUMS:
            return "blue"
        return "green"

    def invert_numbers(self, numbers: Iterable[int]) -> List[int]:
        """取号码反码（1-49中排除指定号码后的其余号码）"""
        excluded: Set[int] = set(int(x) for x in numbers)
        return [i for i in range(1, 50) if i not in excluded]

    def invert_zodiacs(self, zodiacs: Iterable[str]) -> List[str]:
        """取生肖反码（12生肖中排除指定生肖后的其余生肖）"""
        excluded: Set[str] = set(zodiacs)
        return [z for z in self.ZODIAC_SEQUENCE if z not in excluded]

    def invert_str(self, target_str: str) -> str:
        """对应原 VBA 取反码(号码或生肖)"""
        target_str = target_str.strip()
        if not target_str:
            return ""
        if target_str[0].isdigit():
            nums = self.parse_nums_str(target_str)
            inv = self.invert_numbers(nums)
            return self.format_nums(inv)
        else:
            parts = [p.strip() for p in target_str.split(",") if p.strip()]
            inv_z = self.invert_zodiacs(parts)
            return ",".join(inv_z)

    def resolve_selection(self, tags: List[str], mode: str = "auto") -> List[int]:
        """
        选号助手多条件解析：
        - mode == "union": 所有选中标签号码的并集
        - mode == "intersection": 所有选中标签号码的交集
        - mode == "auto" (原Excel选号助手逻辑): 如果多个标签之间存在重复号码，取出现次数>1的交集；否则取并集
        """
        if not tags:
            return []
        counts: Dict[int, int] = {}
        sets: List[Set[int]] = []
        for t in tags:
            nums = self.get_numbers_by_tag(t)
            if nums:
                sets.append(set(nums))
                for n in nums:
                    counts[n] = counts.get(n, 0) + 1
        if not sets:
            return []

        if mode == "union":
            res = sorted(counts.keys())
            return res
        elif mode == "intersection":
            common = set.intersection(*sets)
            return sorted(common)
        else:
            # auto (original VBA logic in 选号助手_模块.bas)
            repeated = [n for n, c in counts.items() if c > 1]
            if repeated:
                return sorted(repeated)
            return sorted(counts.keys())

    def resolve_multi_tags(self, tags: List[str], intersection: bool = True) -> List[int]:
        """根据多条件标签求交集或并集"""
        return self.resolve_selection(tags, mode="intersection" if intersection else "union")
