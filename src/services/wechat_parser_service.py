"""
微信/QQ聊天记录智能识别服务 (WeChatParserService)
完整复刻并优化原 Excel VBA 中的 `微信提取_a总识别模块`、`微信提取_a特码识别模块`、
`微信提取_c替换模块`、`微信提取_数量计算模块`、`微信提取_z反码模块` 等全部核心识别逻辑。
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Set, Tuple
from src.domain.attribute_engine import NumberAttributeEngine
from src.domain.models import AppConfig, BetMode, ParsedBetItem, ReplaceRule, SuiMode
from .chinese_num_converter import ChineseNumberConverter


class WeChatParserService:
    """
    面向对象微信/QQ报单文本智能解析引擎
    """

    # 内置高频关键字兜底集合（同时支持从 SQLite keywords 表加载 1956+ 条关键字）
    DEFAULT_KEYWORDS_EACH_NUM = [
        "各每一个数字各", "各每一个数字个", "个每一个数字个", "个每一个数字各",
        "各每一个号码各", "各每一个号码个", "个每一个号码个", "个每一个号码各",
        "各每一位数字各", "各每一位数字个", "个每一位数字各", "个每一位数字个",
        "每个数字各下", "一个数字各下", "一个号码各下", "每一位数各下", "每一位数各买",
        "一个号码各买", "一个数字各买", "每个号码买", "每个数字买", "每个数买", "每个号买",
        "每个数字各", "一个数字各", "每一位数各", "每个号码各", "一个号码各",
        "各每个数各", "各每位数下", "各每个号码", "各一个号码", "各每位数字", "各每粒数字",
        "每个号各", "每号各", "一个号各", "一号各", "每个数各", "每数各", "每位数各",
        "各每位", "各数各", "一个数各", "一位数各", "每位数下", "每个码各", "一个码各",
        "每个数字", "一个数字", "每个号码", "一个号码", "每位数", "每个数", "每个号",
        "各位数", "各每位数", "各位数各", "每位各", "个数各", "位数各码", "以上各",
        "一个数", "一位数", "个数个", "一个码", "每个码", "一个号", "一个各",
        "=各号", "各号码", "号码各", "号码买", "各下注",
        "各码", "个码", "各数", "个数", "各号", "个号", "各位", "个位", "各个", "个个",
        "每位", "每号", "每数", "每粒", "各粒", "一粒", "号各", "号买", "各买", "每个", "一个", "位数",
        "=各", "各=", "各＝", "＝各", "≈各", "各≈", "=个", "个=", "个＝", "＝个",
    ]

    DEFAULT_KEYWORDS_EACH_ZODIAC = [
        "各每个生肖", "个每个生肖", "一个生肖各", "一个生肖个", "一只生肖各", "一只生肖个",
        "每只生肖各", "每只生肖个", "各一个生肖", "个一个生肖", "各一只生肖", "个一只生肖",
        "各每只生肖", "个每只生肖", "各只生肖各", "各个生肖各", "每个生肖各", "每个生肖个",
        "各每个肖各", "个每个肖个", "各每个肖个", "个每个肖各", "各一只肖各", "个一只肖个",
        "各每只肖各", "个每只肖个", "包特肖各", "包特肖个", "每只生肖", "一只生肖",
        "每个生肖", "各个生肖", "一个生肖", "每只肖各", "每只肖个", "每个肖各", "每个肖个",
        "包肖各", "包肖个", "包特肖", "各特肖", "个特肖", "特肖各", "特肖个",
        "每肖各", "每肖个", "各生肖", "生肖各", "个生肖", "生肖个", "各个肖", "个个肖",
        "每只肖", "每个肖", "一个肖", "一只肖", "一肖买", "包肖", "每肖", "肖各", "各肖", "肖个", "个肖", "各包",
    ]

    DEFAULT_KEYWORDS_TOTAL = [
        "特六肖共", "特6肖共", "6肖中特", "六肖中特", "包6肖", "包六肖", "六肖共", "6肖共",
        "六肖包", "6肖包", "六肖中", "6肖中", "六肖", "6肖", "总包", "平摊", "一共", "总共", "共计",
        "下注", "单调", "单钓", "单吊", "共", "落", "下", "压", "来", "搞", "包", "买", "要", "押", "放", "是",
        "≈", "=", "＝",
    ]

    def __init__(
        self,
        attr_engine: NumberAttributeEngine,
        config: Optional[AppConfig] = None,
        keywords_map: Optional[Dict[str, List[str]]] = None,
        replace_rules: Optional[List[ReplaceRule]] = None,
    ) -> None:
        self.attr_engine = attr_engine
        self.config = config or AppConfig()
        self._keywords_map: Dict[str, List[str]] = {}
        self._each_zodiac_set: Set[str] = set()
        self._each_num_set: Set[str] = set()
        self._total_set: Set[str] = set()
        self._all_keywords_sorted: List[str] = []
        self._replace_rules: List[ReplaceRule] = replace_rules or []
        self.update_keywords(keywords_map or {})

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def update_replace_rules(self, rules: List[ReplaceRule]) -> None:
        self._replace_rules = list(rules)

    def update_keywords(self, keywords_map: Dict[str, List[str]]) -> None:
        each_z = set(self.DEFAULT_KEYWORDS_EACH_ZODIAC)
        each_n = set(self.DEFAULT_KEYWORDS_EACH_NUM)
        tot = set(self.DEFAULT_KEYWORDS_TOTAL)

        if "关键字-各肖" in keywords_map:
            each_z.update(k for k in keywords_map["关键字-各肖"] if k)
        if "关键字-各号" in keywords_map:
            each_n.update(k for k in keywords_map["关键字-各号"] if k)
        if "关键字-共" in keywords_map:
            tot.update(k for k in keywords_map["关键字-共"] if k)

        all_kw = set(each_z) | set(each_n) | set(tot) | {"各", "个", "号", "肖", "x", "×"}
        if "全部关键字" in keywords_map:
            all_kw.update(k for k in keywords_map["全部关键字"] if k)

        self._each_zodiac_set = each_z
        self._each_num_set = each_n
        self._total_set = tot
        self._all_keywords_sorted = sorted(all_kw, key=lambda x: (-len(x), x))

    def is_each_zodiac_keyword(self, kw: str) -> bool:
        return kw in self._each_zodiac_set

    def is_each_num_keyword(self, kw: str) -> bool:
        return kw in self._each_num_set

    def is_total_keyword(self, kw: str) -> bool:
        return kw in self._total_set

    def calculate_divisor(
        self,
        single_tag: str,
        keyword: str,
        tag_count: int,
        all_tags_list: Optional[List[str]] = None,
    ) -> int:
        """
        对应原 VBA `微信提取_数量计算模块.bas` -> `计算数量(单个生肖, 关键字, 生肖数量, 原始生肖字符串)`
        返回将输入金额平摊到单个号码时的除数：
        - 若除数为 1，表示每个号码都得 `金额`（各号）
        - 若除数为 len(生肖号码)，表示该生肖/属性总共享 `金额`（各肖）
        - 若除数为 所有生肖合并去重前的总号码数，表示多个生肖合买平摊 `金额`（共/平摊）
        """
        tag_nums = self.attr_engine.get_numbers_by_tag(single_tag)
        tag_num_len = max(1, len(tag_nums))

        if self.is_each_zodiac_keyword(keyword):
            return tag_num_len
        if self.is_total_keyword(keyword):
            if all_tags_list and len(all_tags_list) > 0:
                total_len = sum(len(self.attr_engine.get_numbers_by_tag(t)) for t in all_tags_list)
                return max(1, total_len)
            return tag_num_len
        if self.is_each_num_keyword(keyword):
            return 1

        # 对于未明确归入前三类的中性词（如 "各"、"个"、"号"）：根据当前版本模式决定
        if tag_count == 1:
            if self.config.bet_mode == BetMode.EACH_ZODIAC_SINGLE_ZODIAC:
                return tag_num_len
            return 1
        else:
            if self.config.bet_mode in (BetMode.EACH_ZODIAC_SINGLE_ZODIAC, BetMode.EACH_ZODIAC_SINGLE_NUM):
                return tag_num_len
            return 1

    def preprocess_text(self, text: str) -> str:
        """
        对应原 VBA `替换_内容替换(内容)`：
        1. 应用用户自定义文字替换规则
        2. 清理微信昵称前缀、期数、无关词（天天彩、总单等）
        3. 规范化同义词、错别字、繁体字、区间（1到25）、多岁数（1岁5岁 -> 1,5岁）
        """
        if not text:
            return ""
        s = text

        # 1. 应用自定义替换规则
        for rule in self._replace_rules:
            if rule.is_enabled and rule.find_text:
                s = s.replace(rule.find_text, rule.replace_text)

        # 2. 清理微信头部形如 "张三:\n"
        s = re.sub(r"(?:^|\n)[^\s\d中肖连:：]{1,12}[:：]\s*(?=\n)", "\n", s)

        # 3. 清理期数和彩种词
        for word in ("天天彩", "天天采", "天天", "天彩", "天采", "总单", "澳门特肖", "澳门特"):
            s = s.replace(word, " ")
        s = re.sub(r"(?:新澳门|旧澳门|老澳门|澳门|香港)\d*期", " ", s)

        # 4. 常见同义词与错别字归一化（对应 替换_内容替换）
        for z in NumberAttributeEngine.ZODIAC_SEQUENCE:
            s = s.replace(f"{z}肉", z)

        char_map = {
            "O": "0", "o": "0", "〇": "0", "Ⅰ": "1",
            "午": "牛", "免": "兔", "拘": "狗", "馬": "马", "龍": "龙",
            "雞": "鸡", "鳮": "鸡", "豬": "猪", "候": "猴", "侯": "猴",
            "坡": "波", "泼": "波", "篮": "蓝", "単": "单", "組": "组",
            "數": "数", "號": "号", "碼": "码", "壓": "压", "持": "特",
            "壹": "一", "贰": "二", "叁": "三", "肆": "四", "伍": "五",
            "陆": "六", "柒": "七", "捌": "八", "玖": "九", "拾": "十",
            "佰": "百", "仟": "千", "≡": "三", "俩": "二",
        }
        for k, v in char_map.items():
            s = s.replace(k, v)

        phrase_map = [
            ("共共", "共"),
            ("4.岁", "4岁"),
            ("個數", "个数"),
            ("老鼠", "鼠"), ("老虎", "虎"), ("老蛇", "蛇"),
            ("兔子", "兔"), ("猴子", "猴"),
            ("家肖", "家禽"), ("家畜", "家禽"),
            ("野肖", "野兽"),
            ("单号", "单"), ("双号", "双"), ("大号", "大"), ("小号", "小"),
            ("大数", "大"), ("小数", "小"), ("双数", "双"), ("单数", "单"),
            ("合数小", "合小"), ("合数大", "合大"),
            ("单大", "大单"), ("单小", "小单"), ("双大", "大双"), ("双小", "小双"),
            ("红波小", "红小"), ("红波小数", "红小"), ("红波大", "红大"), ("红波大数", "红大"),
            ("绿波小", "绿小"), ("绿波小数", "绿小"), ("绿波大", "绿大"), ("绿波大数", "绿大"),
            ("蓝波小", "蓝小"), ("蓝波小数", "蓝小"), ("兰小", "蓝小"), ("兰波小", "蓝小"), ("兰波小数", "蓝小"),
            ("蓝波大", "蓝大"), ("蓝波大数", "蓝大"), ("兰大", "蓝大"), ("兰波大", "蓝大"), ("兰波大数", "蓝大"),
            ("尾数小", "小尾"), ("尾数大", "大尾"), ("尾数", "尾"),
            ("特六肖共", "共"), ("平摊", "共"),
            ("//", "/"),
        ]
        for old_p, new_p in phrase_map:
            s = s.replace(old_p, new_p)

        # 5. 区间展开：如 "1到25" 或 "10至42" -> "01,02,...,25"
        def _expand_range(m: re.Match) -> str:
            n1 = int(ChineseNumberConverter.to_num(m.group(1)))
            n2 = int(ChineseNumberConverter.to_num(m.group(2)))
            n1 = max(1, min(49, n1))
            n2 = max(1, min(49, n2))
            if n1 <= n2:
                return ",".join(f"{i:02d}" for i in range(n1, n2 + 1))
            return m.group(0)

        s = re.sub(
            r"(\d{1,2}|[一二三四五六七八九十]+)号?\s*[到至]\s*(\d{1,2}|[一二三四五六七八九十]+)号?",
            _expand_range,
            s,
        )

        # 6. 多岁数合并：如 "10岁，4岁各300" -> "10,4岁各300"
        def _merge_sui(m: re.Match) -> str:
            nums = re.findall(r"\d+", m.group(0))
            return ",".join(nums) + "岁"

        s = re.sub(r"(?:\d+\s*岁[,，。./\\\- ]*){2,}", _merge_sui, s)

        # 7. 处理 "一5" -> "-5", "二5" -> "=5", "3十5" (当两数字间夹十且非金额时)
        s = re.sub(r"(?<=\d)一(?=\d)", "-", s)
        s = re.sub(r"(?<=\d)二(?=\d)", "=", s)

        # 8. 清理末尾如 "合计：500"、"共計1000元" 等总结词（注意保留 "大共500"、"牛共400" 中的共）
        s = re.sub(r"(?:一起|和计|总合|一共|总共|加总|汇总|总和|总计|共计|合计)[：:\s]*\d+(?:\.\d+)?[元斤米咪闷皮块]?", " ", s)

        return s.strip()

    def _get_tag_regex_pattern(self) -> str:
        """构建所有可识别的生肖与属性组合词正则（按长度降序）"""
        ca_keys = [k for k in self.attr_engine.get_ca_dict().keys() if not k.isdigit()]
        if self.config.sui_mode != SuiMode.SUI_ZODIAC:
            # 在 岁模式_各 下，单岁数仍可通过头尾岁分支或属性识别
            pass
        sorted_keys = sorted(ca_keys, key=lambda x: (-len(x), x))
        escaped = [re.escape(k) for k in sorted_keys]
        return "(?:" + "|".join(escaped) + ")"

    def _get_keyword_regex_pattern(self) -> str:
        escaped = [re.escape(k) for k in self._all_keywords_sorted if k]
        return "(?:" + "|".join(escaped) + ")"

    def parse_text(self, raw_text: str) -> List[ParsedBetItem]:
        """
        核心智能识别入口：将任意多行或单行微信/QQ报单文本解析为 `List[ParsedBetItem]`
        """
        if not raw_text or not raw_text.strip():
            return []

        cleaned = self.preprocess_text(raw_text)
        items: List[ParsedBetItem] = []

        # 按换行或明显句界切分，逐行/逐段解析以保证原始顺序并支持同段多单
        lines = [line.strip() for line in re.split(r"[\r\n]+", cleaned) if line.strip()]
        for line in lines:
            line_items = self._parse_single_line(line)
            items.extend(line_items)

        for item in items:
            item.validate()
        return items

    def _parse_single_line(self, line: str) -> List[ParsedBetItem]:
        """解析单行报单文本（支持一行内包含多个报单子句）"""
        results: List[ParsedBetItem] = []
        working = line.strip()
        if not working:
            return results

        amt_num_pat = r"-?\d+(?:\.\d+)?" if self.config.recognize_decimal else r"-?\d+"
        amt_cn_pat = r"[一二三四五六七八九十百千万两拾佰仟零〇]+"
        amt_pat = f"(?:{amt_num_pat}|{amt_cn_pat})"
        unit_pat = r"[元斤米咪闷皮块门）\)]*"
        kw_pat = self._get_keyword_regex_pattern()
        tag_pat = self._get_tag_regex_pattern()

        # ------------------------------------------------------------------
        # Step 0: 标准回放格式快捷识别，如 "04,16,28,40各25"
        # ------------------------------------------------------------------
        m_canon = re.fullmatch(r"((?:\d{1,2}[,，])*\d{1,2})各(-?\d+(?:\.\d+)?)", working)
        if m_canon:
            nums = [int(x) for x in re.findall(r"\d+", m_canon.group(1))]
            amt = float(m_canon.group(2))
            results.append(
                ParsedBetItem(
                    numbers=nums,
                    per_number_amount=round(amt, 3),
                    total_amount=round(amt * len(nums), 2),
                    raw_fragment=working,
                )
            )
            return results

        # ------------------------------------------------------------------
        # Step 1: 特殊复合模式 - 几头/几尾带单双（如 "0.1.2头单各50"、"123头双各30"）
        # ------------------------------------------------------------------
        pat_head_parity = re.compile(
            rf"([\d\.\-\/\\，,、\s]+)(头(?:单数|双数|单|双))[,，。.\s、\-]*({kw_pat})?\s*({amt_pat}){unit_pat}"
        )
        for m in list(pat_head_parity.finditer(working)):
            digits = re.findall(r"\d", m.group(1))
            if not digits:
                continue
            suffix = "头单" if "单" in m.group(2) else "头双"
            kw = m.group(3) or "各"
            amt = ChineseNumberConverter.to_num(m.group(4))
            tags = [f"{d}{suffix}" for d in digits if self.attr_engine.get_numbers_by_tag(f"{d}{suffix}")]
            for t in tags:
                t_nums = self.attr_engine.get_numbers_by_tag(t)
                div = self.calculate_divisor(t, kw, len(tags), tags)
                per_amt = round(amt / max(1, div), 3)
                results.append(
                    ParsedBetItem(
                        numbers=t_nums,
                        per_number_amount=per_amt,
                        total_amount=round(per_amt * len(t_nums), 2),
                        raw_fragment=m.group(0).strip(),
                    )
                )
        working = pat_head_parity.sub(" ", working)

        # ------------------------------------------------------------------
        # Step 2: 特殊复合模式 - 红蓝绿波带单双（如 "红蓝单各50"、"红绿波双各100"）
        # ------------------------------------------------------------------
        pat_wave_parity = re.compile(
            rf"((?:红波|[蓝兰]波|绿波|红|蓝|绿|兰){{2,}})(单数|双数|单|双)[,，。.\s、\-]*({kw_pat})?\s*({amt_pat}){unit_pat}"
        )
        for m in list(pat_wave_parity.finditer(working)):
            waves = re.findall(r"(?:红波|[蓝兰]波|绿波|红|蓝|绿|兰)", m.group(1))
            parity = "单" if "单" in m.group(2) else "双"
            kw = m.group(3) or "各"
            amt = ChineseNumberConverter.to_num(m.group(4))
            tags = []
            for w in waves:
                color = "红" if "红" in w else ("蓝" if ("蓝" in w or "兰" in w) else "绿")
                tags.append(f"{color}{parity}")
            for t in tags:
                t_nums = self.attr_engine.get_numbers_by_tag(t)
                div = self.calculate_divisor(t, kw, len(tags), tags)
                per_amt = round(amt / max(1, div), 3)
                results.append(
                    ParsedBetItem(
                        numbers=t_nums,
                        per_number_amount=per_amt,
                        total_amount=round(per_amt * len(t_nums), 2),
                        raw_fragment=m.group(0).strip(),
                    )
                )
        working = pat_wave_parity.sub(" ", working)

        # ------------------------------------------------------------------
        # Step 3: 多头/多尾/多岁/多合识别
        # 支持：
        # (a) "3头4头每个数10"、"4尾，5尾，6尾，8尾每个数各15"、"1岁5岁每个数10"
        # (b) "014头各50"、"23789尾各90"、"1.3.4头各100"、"1-2-3-10岁各50"、"特码尾数1234，每个数各20"
        # ------------------------------------------------------------------
        pat_multi_ht_explicit = re.compile(
            rf"((?:\d+\s*[头尾岁合][,，。.、/\-\\ ]*){{2,}})({kw_pat})\s*({amt_pat}){unit_pat}"
        )
        for m in list(pat_multi_ht_explicit.finditer(working)):
            pairs = re.findall(r"(\d+)\s*([头尾岁合])", m.group(1))
            kw = m.group(2)
            amt = ChineseNumberConverter.to_num(m.group(3))
            tags = [f"{int(num_s)}{kind}" for num_s, kind in pairs if self.attr_engine.get_numbers_by_tag(f"{int(num_s)}{kind}")]
            for t in tags:
                t_nums = self.attr_engine.get_numbers_by_tag(t)
                div = self.calculate_divisor(t, kw, len(tags), tags)
                per_amt = round(amt / max(1, div), 3)
                results.append(
                    ParsedBetItem(
                        numbers=t_nums,
                        per_number_amount=per_amt,
                        total_amount=round(per_amt * len(t_nums), 2),
                        raw_fragment=m.group(0).strip(),
                    )
                )
        working = pat_multi_ht_explicit.sub(" ", working)

        pat_multi_ht_compact = re.compile(
            rf"(?:特码?尾数?)?((?:\d+[\.\-\/\\，,、\s]+)+\d+|\d{{2,}})(头|尾|岁|合)[,，。.、\s]*({kw_pat})\s*({amt_pat}){unit_pat}"
        )
        for m in list(pat_multi_ht_compact.finditer(working)):
            raw_nums_part = m.group(1)
            kind = m.group(2)
            kw = m.group(3)
            amt = ChineseNumberConverter.to_num(m.group(4))
            extracted: List[int] = []
            for chunk in re.findall(r"\d+", raw_nums_part):
                val = int(chunk)
                if kind in ("头", "尾") or (kind == "岁" and val > 12) or (kind == "合" and val > 13):
                    for ch in chunk:
                        extracted.append(int(ch))
                else:
                    extracted.append(val)
            tags = [f"{n}{kind}" for n in extracted if self.attr_engine.get_numbers_by_tag(f"{n}{kind}")]
            for t in tags:
                t_nums = self.attr_engine.get_numbers_by_tag(t)
                div = self.calculate_divisor(t, kw, len(tags), tags)
                per_amt = round(amt / max(1, div), 3)
                results.append(
                    ParsedBetItem(
                        numbers=t_nums,
                        per_number_amount=per_amt,
                        total_amount=round(per_amt * len(t_nums), 2),
                        raw_fragment=m.group(0).strip(),
                    )
                )
        working = pat_multi_ht_compact.sub(" ", working)

        # ------------------------------------------------------------------
        # Step 4: 将一行中按常见子句分隔或连续匹配识别：
        # 支持：
        # - 生肖/属性组合 + 关键字 + 金额（如 "牛虎兔各码25"、"羊狗各五"、"兔.蛇.猴各数50"、"大共500元"、"反码鼠牛各10"）
        # - 号码列表 + 关键字 + 金额（如 "18-35-47各20"、"23   5  27   2一个5块"、"1，30，42各5米"、"7.各50"、"19/各10"）
        # - 单号+分隔符+金额（无"各"字，如 "22/10"、"10-10"、"23.166元"、"1，。10米"、"19 30"）
        # - 生肖/属性直接加金额（无"各"字，如 "兰波300"、"鸡30"、"牛虎50"）
        # ------------------------------------------------------------------
        clause_tokens = self._extract_clauses(working, tag_pat, kw_pat, amt_pat, unit_pat)
        results.extend(clause_tokens)
        return results

    def _extract_clauses(
        self,
        text: str,
        tag_pat: str,
        kw_pat: str,
        amt_pat: str,
        unit_pat: str,
    ) -> List[ParsedBetItem]:
        items: List[ParsedBetItem] = []
        rem = text.strip()
        if not rem:
            return items

        tag_finder = re.compile(tag_pat)

        # 4A. 生肖/属性列表 + 关键字 + 金额（或 生肖与号码混合 + 关键字 + 金额）
        pat_tags_kw = re.compile(
            rf"(反码)?((?:{tag_pat}[,，。.、/\-\\\s]*)+)[,，。.、/\-\\\s]*({kw_pat})[,，。.、/\-\\\s：:（\(]*({amt_pat}){unit_pat}"
        )
        # 4B. 号码列表 + 关键字 + 金额
        pat_nums_kw = re.compile(
            rf"(反码)?((?:\d{{1,2}}[,，。.、/\-\\\s—–]+)*\d{{1,2}})[,，。.、/\-\\\s—–]*({kw_pat})[,，。.、/\-\\\s：:（\(]*({amt_pat}){unit_pat}"
        )
        # 4C. 单号 + 点/杠/斜杠/逗号/空格 + 金额（无关键字，如 "22/10", "23.166元", "10-10", "1，。10米"）
        pat_single_num_sep_amt = re.compile(
            rf"(?:^|(?<=[\s,，;；]))(0?[1-9]|[1-4][0-9])(?:[,，。.\-/\\：:]+|\s+)({amt_pat}){unit_pat}(?=$|[\s,，;；])"
        )
        # 4D. 多号码用连字符/斜杠/逗号分隔 + 空格/等号 + 金额（无关键字）
        pat_multi_num_no_kw = re.compile(
            rf"(反码)?((?:(?:0?[1-9]|[1-4][0-9])[,，.、/\-\\]+)+(?:0?[1-9]|[1-4][0-9]))[\s=＝:：]+({amt_pat}){unit_pat}"
        )
        # 4E. 生肖/属性 + 金额（无关键字，如 "兰波300", "鸡30"）
        pat_tags_no_kw = re.compile(
            rf"(反码)?((?:{tag_pat}[,，。.、/\-\\\s]*)+)[,，。.、/\-\\\s]*({amt_pat}){unit_pat}"
        )

        # 为了严格保持文本从左到右的出现顺序，我们扫描最早匹配项
        pos = 0
        n = len(rem)
        while pos < n:
            sub = rem[pos:]
            candidates: List[Tuple[int, int, str, re.Match]] = []

            m_tk = pat_tags_kw.search(sub)
            if m_tk:
                candidates.append((m_tk.start(), -len(m_tk.group(0)), "tags_kw", m_tk))

            m_nk = pat_nums_kw.search(sub)
            if m_nk:
                candidates.append((m_nk.start(), -len(m_nk.group(0)), "nums_kw", m_nk))

            m_mn = pat_multi_num_no_kw.search(sub)
            if m_mn:
                candidates.append((m_mn.start(), -len(m_mn.group(0)), "multi_num_no_kw", m_mn))

            m_sn = pat_single_num_sep_amt.search(sub)
            if m_sn:
                candidates.append((m_sn.start(), -len(m_sn.group(0)), "single_num_no_kw", m_sn))

            m_tn = pat_tags_no_kw.search(sub)
            if m_tn:
                candidates.append((m_tn.start(), -len(m_tn.group(0)), "tags_no_kw", m_tn))

            if not candidates:
                break

            # 选择起始位置最靠前、且匹配长度最长的候选；若同起点，带关键字的优先于不带关键字的
            priority_map = {
                "tags_kw": 0,
                "nums_kw": 0,
                "multi_num_no_kw": 1,
                "single_num_no_kw": 2,
                "tags_no_kw": 3,
            }
            candidates.sort(key=lambda x: (x[0], priority_map[x[2]], x[1]))
            _, _, kind, best_m = candidates[0]

            if kind == "tags_kw":
                is_inv = bool(best_m.group(1))
                raw_tags_str = best_m.group(2)
                kw = best_m.group(3)
                amt = ChineseNumberConverter.to_num(best_m.group(4))
                tags = tag_finder.findall(raw_tags_str)
                if is_inv and all(t in NumberAttributeEngine.ZODIAC_SEQUENCE for t in tags):
                    tags = self.attr_engine.invert_zodiacs(tags)
                for t in tags:
                    t_nums = self.attr_engine.get_numbers_by_tag(t)
                    if is_inv and t not in NumberAttributeEngine.ZODIAC_SEQUENCE:
                        t_nums = self.attr_engine.invert_numbers(t_nums)
                    div = self.calculate_divisor(t, kw, len(tags), tags)
                    per_amt = round(amt / max(1, div), 3)
                    items.append(
                        ParsedBetItem(
                            numbers=t_nums,
                            per_number_amount=per_amt,
                            total_amount=round(per_amt * len(t_nums), 2),
                            raw_fragment=best_m.group(0).strip(),
                        )
                    )
            elif kind == "nums_kw":
                is_inv = bool(best_m.group(1))
                raw_nums_str = best_m.group(2)
                kw = best_m.group(3)
                amt = ChineseNumberConverter.to_num(best_m.group(4))
                nums = [int(x) for x in re.findall(r"\d+", raw_nums_str)]
                if is_inv:
                    nums = self.attr_engine.invert_numbers(nums)
                if nums:
                    is_flat = self.is_total_keyword(kw) and ("各" not in kw and "个" not in kw)
                    per_amt = round(amt / len(nums), 3) if is_flat else round(amt, 3)
                    items.append(
                        ParsedBetItem(
                            numbers=nums,
                            per_number_amount=per_amt,
                            total_amount=round(per_amt * len(nums), 2),
                            raw_fragment=best_m.group(0).strip(),
                        )
                    )
            elif kind == "multi_num_no_kw":
                is_inv = bool(best_m.group(1))
                raw_nums_str = best_m.group(2)
                amt = ChineseNumberConverter.to_num(best_m.group(3))
                nums = [int(x) for x in re.findall(r"\d+", raw_nums_str)]
                if is_inv:
                    nums = self.attr_engine.invert_numbers(nums)
                if nums:
                    is_flat = "=" in best_m.group(0) or "＝" in best_m.group(0)
                    per_amt = round(amt / len(nums), 3) if is_flat else round(amt, 3)
                    items.append(
                        ParsedBetItem(
                            numbers=nums,
                            per_number_amount=per_amt,
                            total_amount=round(per_amt * len(nums), 2),
                            raw_fragment=best_m.group(0).strip(),
                        )
                    )
            elif kind == "single_num_no_kw":
                num = int(best_m.group(1))
                amt = ChineseNumberConverter.to_num(best_m.group(2))
                items.append(
                    ParsedBetItem(
                        numbers=[num],
                        per_number_amount=round(amt, 3),
                        total_amount=round(amt, 2),
                        raw_fragment=best_m.group(0).strip(),
                    )
                )
            elif kind == "tags_no_kw":
                is_inv = bool(best_m.group(1))
                raw_tags_str = best_m.group(2)
                amt = ChineseNumberConverter.to_num(best_m.group(3))
                tags = tag_finder.findall(raw_tags_str)
                if is_inv and all(t in NumberAttributeEngine.ZODIAC_SEQUENCE for t in tags):
                    tags = self.attr_engine.invert_zodiacs(tags)
                for t in tags:
                    t_nums = self.attr_engine.get_numbers_by_tag(t)
                    if is_inv and t not in NumberAttributeEngine.ZODIAC_SEQUENCE:
                        t_nums = self.attr_engine.invert_numbers(t_nums)
                    div = self.calculate_divisor(t, "=", 1, [t])
                    per_amt = round(amt / max(1, div), 3)
                    items.append(
                        ParsedBetItem(
                            numbers=t_nums,
                            per_number_amount=per_amt,
                            total_amount=round(per_amt * len(t_nums), 2),
                            raw_fragment=best_m.group(0).strip(),
                        )
                    )

            pos += best_m.end()

        return items

    @staticmethod
    def negate_items(items: List[ParsedBetItem]) -> List[ParsedBetItem]:
        """一键负数（用于撤单扣减之前已添加的订单）"""
        for item in items:
            item.per_number_amount = -abs(item.per_number_amount)
            item.total_amount = -abs(item.total_amount)
        return items

    @staticmethod
    def parse_canonical_order_content(parsed_content: str) -> Dict[int, float]:
        """
        从订单明细中的标准 `parsed_content`（如 '04,16,28,40各25\\n09,21,33,45各5'）
        解析出每个号码(1-49)对应的累计金额字典 `{number: amount}`。
        注意：若同一行有重复号码（如 '14,10,23,14,26各10'），会按出现次数累加，与原 Excel 完全一致！
        """
        number_totals: Dict[int, float] = {}
        pattern = re.compile(r"([^各\r\n]+)各(-?\d+(?:\.\d+)?)")
        for m in pattern.finditer(parsed_content or ""):
            nums_part = m.group(1)
            amt = float(m.group(2))
            for n_str in re.findall(r"\d+", nums_part):
                n = int(n_str)
                if 1 <= n <= 49:
                    number_totals[n] = round(number_totals.get(n, 0.0) + amt, 2)
        return number_totals

    def parse_quick_input(self, code_str: str, amount: float, is_flat: bool = False) -> Optional[ParsedBetItem]:
        """
        极速录入解析（对应 `单号快速输入.frm` 与 `多号快速输入.frm`）：
        - 支持输入混合生肖/属性与两位数字（如 "兔蛇0112" -> 兔、蛇对应号码 + 01, 12）
        - 支持 每注(is_flat=False) 或 平摊(is_flat=True)
        """
        code_str = code_str.strip()
        if not code_str or amount == 0:
            return None

        tag_pat = self._get_tag_regex_pattern()
        tag_finder = re.compile(tag_pat)

        matched_nums: List[int] = []
        for m in tag_finder.finditer(code_str):
            matched_nums.extend(self.attr_engine.get_numbers_by_tag(m.group(0)))

        rem_digits = re.sub(r"\D", "", tag_finder.sub("", code_str))
        # 按两位数字切分，若只有1-2位直接解析
        if len(rem_digits) in (1, 2):
            val = int(rem_digits)
            if 1 <= val <= 49:
                matched_nums.append(val)
        else:
            for i in range(0, len(rem_digits) - 1, 2):
                val = int(rem_digits[i : i + 2])
                if 1 <= val <= 49:
                    matched_nums.append(val)

        if not matched_nums:
            return None

        if is_flat:
            per_amt = round(amount / len(matched_nums), 2)
            tot_amt = round(amount, 2)
        else:
            per_amt = round(amount, 2)
            tot_amt = round(amount * len(matched_nums), 2)

        item = ParsedBetItem(
            numbers=matched_nums,
            per_number_amount=per_amt,
            total_amount=tot_amt,
            raw_fragment=f"{','.join(f'{n:02d}' for n in matched_nums)}{'平摊' if is_flat else '各'}{amount:g}",
        )
        item.validate()
        return item
