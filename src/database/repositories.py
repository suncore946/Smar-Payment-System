"""
面向对象数据仓储类 (Repository Layer)
将 SQLite 读写操作封装为强类型的领域对象访问接口
"""

from __future__ import annotations
from datetime import datetime
import json
from typing import Dict, List, Optional, Tuple
from src.domain.models import (
    AppConfig,
    BookmakerRecord,
    ClientProfile,
    DailyArchiveRecord,
    OrderRecord,
    RegionConfig,
    ReplaceRule,
)
from .db_manager import DatabaseManager


class BaseRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db


class ConfigRepository(BaseRepository):
    """全局配置与自定义属性字典覆盖仓储"""

    ATTR_PREFIX = "attr_override:"

    def load_app_config(self) -> AppConfig:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT key, value FROM app_config WHERE key NOT LIKE ?",
                (f"{self.ATTR_PREFIX}%",),
            ).fetchall()
            data = {r["key"]: r["value"] for r in rows}
            return AppConfig.from_dict(data)

    def save_app_config(self, config: AppConfig) -> None:
        data = config.to_dict()
        with self._db.connection() as conn:
            conn.executemany(
                "INSERT INTO app_config(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                list(data.items()),
            )

    def load_attribute_overrides(self) -> Dict[str, str]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT key, value FROM app_config WHERE key LIKE ?",
                (f"{self.ATTR_PREFIX}%",),
            ).fetchall()
            prefix_len = len(self.ATTR_PREFIX)
            return {r["key"][prefix_len:]: r["value"] for r in rows}

    def save_attribute_override(self, tag: str, numbers_str: str) -> None:
        key = f"{self.ATTR_PREFIX}{tag}"
        with self._db.connection() as conn:
            if not numbers_str.strip():
                conn.execute("DELETE FROM app_config WHERE key = ?", (key,))
            else:
                conn.execute(
                    "INSERT INTO app_config(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, numbers_str.strip()),
                )

    def clear_all_attribute_overrides(self) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "DELETE FROM app_config WHERE key LIKE ?",
                (f"{self.ATTR_PREFIX}%",),
            )

    def save_attribute_overrides(self, overrides: Dict[str, str | List[int]]) -> None:
        self.clear_all_attribute_overrides()
        for tag, val in overrides.items():
            if isinstance(val, str):
                s = val
            else:
                s = ",".join(f"{int(n):02d}" for n in val)
            self.save_attribute_override(tag, s)


class RegionRepository(BaseRepository):
    """地区/盘口（新澳门、旧澳门、香港等）仓储"""

    def list_regions(self) -> List[RegionConfig]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM regions ORDER BY display_order ASC, name ASC"
            ).fetchall()
            return [
                RegionConfig(
                    name=r["name"],
                    display_order=r["display_order"],
                    global_odds=float(r["global_odds"]),
                    global_rebate=float(r["global_rebate"]),
                    active_client_name=r["active_client_name"],
                    last_winning_number=int(r["last_winning_number"]),
                )
                for r in rows
            ]

    def get_region(self, name: str) -> Optional[RegionConfig]:
        with self._db.connection() as conn:
            r = conn.execute("SELECT * FROM regions WHERE name = ?", (name,)).fetchone()
            if not r:
                return None
            return RegionConfig(
                name=r["name"],
                display_order=r["display_order"],
                global_odds=float(r["global_odds"]),
                global_rebate=float(r["global_rebate"]),
                active_client_name=r["active_client_name"],
                last_winning_number=int(r["last_winning_number"]),
            )

    def save_region(self, region: RegionConfig) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO regions(name, display_order, global_odds, global_rebate, active_client_name, last_winning_number)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    display_order = excluded.display_order,
                    global_odds = excluded.global_odds,
                    global_rebate = excluded.global_rebate,
                    active_client_name = excluded.active_client_name,
                    last_winning_number = excluded.last_winning_number
                """,
                (
                    region.name,
                    region.display_order,
                    region.global_odds,
                    region.global_rebate,
                    region.active_client_name,
                    region.last_winning_number,
                ),
            )

    def delete_region(self, name: str) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM regions WHERE name = ?", (name,))
            conn.execute("DELETE FROM clients WHERE region = ?", (name,))
            conn.execute("DELETE FROM orders WHERE region = ?", (name,))
            conn.execute("DELETE FROM eat_report_state WHERE region = ?", (name,))
            conn.execute("DELETE FROM bookmakers WHERE region = ?", (name,))


class ClientRepository(BaseRepository):
    """下单人/客户分人统计仓储"""

    @staticmethod
    def _deserialize_bets(bets_json: str) -> Dict[int, float]:
        bets = {i: 0.0 for i in range(1, 50)}
        try:
            raw = json.loads(bets_json or "{}")
            for k, v in raw.items():
                num = int(k)
                if 1 <= num <= 49:
                    bets[num] = round(float(v), 2)
        except Exception:
            pass
        return bets

    @staticmethod
    def _serialize_bets(bets: Dict[int, float]) -> str:
        compact = {str(k): round(float(v), 2) for k, v in bets.items() if 1 <= int(k) <= 49 and round(float(v), 2) != 0}
        return json.dumps(compact, ensure_ascii=False)

    def list_clients(self, region: str) -> List[ClientProfile]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM clients WHERE region = ? ORDER BY sort_order ASC, id ASC",
                (region,),
            ).fetchall()
            return [
                ClientProfile(
                    id=r["id"],
                    region=r["region"],
                    name=r["name"],
                    odds=float(r["odds"]),
                    rebate=float(r["rebate"]),
                    sort_order=int(r["sort_order"]),
                    number_bets=self._deserialize_bets(r["bets_json"]),
                )
                for r in rows
            ]

    def get_client(self, region: str, name: str) -> Optional[ClientProfile]:
        with self._db.connection() as conn:
            r = conn.execute(
                "SELECT * FROM clients WHERE region = ? AND name = ?",
                (region, name),
            ).fetchone()
            if not r:
                return None
            return ClientProfile(
                id=r["id"],
                region=r["region"],
                name=r["name"],
                odds=float(r["odds"]),
                rebate=float(r["rebate"]),
                sort_order=int(r["sort_order"]),
                number_bets=self._deserialize_bets(r["bets_json"]),
            )

    def save_client(self, client: ClientProfile) -> None:
        bets_json = self._serialize_bets(client.number_bets)
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO clients(region, name, odds, rebate, sort_order, bets_json)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(region, name) DO UPDATE SET
                    odds = excluded.odds,
                    rebate = excluded.rebate,
                    sort_order = excluded.sort_order,
                    bets_json = excluded.bets_json
                """,
                (
                    client.region,
                    client.name,
                    client.odds,
                    client.rebate,
                    client.sort_order,
                    bets_json,
                ),
            )

    def rename_client(self, region: str, old_name: str, new_name: str) -> bool:
        new_name = new_name.strip()
        if not new_name or new_name[0].isdigit():
            return False
        with self._db.connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM clients WHERE region = ? AND name = ?",
                (region, new_name),
            ).fetchone()
            if exists:
                return False
            conn.execute(
                "UPDATE clients SET name = ? WHERE region = ? AND name = ?",
                (new_name, region, old_name),
            )
            conn.execute(
                "UPDATE orders SET client_name = ? WHERE region = ? AND client_name = ?",
                (new_name, region, old_name),
            )
            conn.execute(
                "UPDATE regions SET active_client_name = ? WHERE name = ? AND active_client_name = ?",
                (new_name, region, old_name),
            )
        return True

    def unify_odds_and_rebate(self, region: str, odds: float, rebate: float) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "UPDATE clients SET odds = ?, rebate = ? WHERE region = ?",
                (odds, rebate, region),
            )

    def add_client_bets(self, region: str, client_name: str, delta_bets: Dict[int, float]) -> None:
        client = self.get_client(region, client_name)
        if not client:
            client = ClientProfile(id=None, region=region, name=client_name, odds=47.0, rebate=0.0, sort_order=999)
        for num, delta in delta_bets.items():
            if 1 <= num <= 49:
                client.number_bets[num] = round(client.number_bets.get(num, 0.0) + delta, 2)
        self.save_client(client)

    def clear_region_bets(self, region: str) -> None:
        with self._db.connection() as conn:
            conn.execute("UPDATE clients SET bets_json = '{}' WHERE region = ?", (region,))

    def get_region_total_bets_by_number(self, region: str) -> Dict[int, float]:
        """计算某盘口所有客户在 1-49 号上的累计押注总金额"""
        totals = {i: 0.0 for i in range(1, 50)}
        clients = self.list_clients(region)
        for c in clients:
            for num, amt in c.number_bets.items():
                if 1 <= num <= 49:
                    totals[num] = round(totals[num] + amt, 2)
        return totals


class OrderRepository(BaseRepository):
    """订单明细记录仓储"""

    def list_orders(
        self,
        region: str,
        client_filter: Optional[str] = None,
        keyword_filter: Optional[str] = None,
    ) -> List[OrderRecord]:
        query = "SELECT * FROM orders WHERE region = ?"
        params: list = [region]
        if client_filter and client_filter != "全部":
            query += " AND client_name = ?"
            params.append(client_filter)
        if keyword_filter and keyword_filter.strip():
            kw = f"%{keyword_filter.strip()}%"
            query += " AND (raw_text LIKE ? OR parsed_content LIKE ? OR client_name LIKE ?)"
            params.extend([kw, kw, kw])
        query += " ORDER BY seq_no ASC, id ASC"

        with self._db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                OrderRecord(
                    id=r["id"],
                    seq_no=int(r["seq_no"]),
                    region=r["region"],
                    client_name=r["client_name"],
                    raw_text=r["raw_text"],
                    parsed_content=r["parsed_content"],
                    total_amount=float(r["total_amount"]),
                    winning_amount=float(r["winning_amount"]),
                    pnl_no_rebate=float(r["pnl_no_rebate"]),
                    rebate_amount=float(r["rebate_amount"]),
                    net_pnl=float(r["net_pnl"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def get_order_by_id(self, order_id: int) -> Optional[OrderRecord]:
        with self._db.connection() as conn:
            r = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not r:
                return None
            return OrderRecord(
                id=r["id"],
                seq_no=int(r["seq_no"]),
                region=r["region"],
                client_name=r["client_name"],
                raw_text=r["raw_text"],
                parsed_content=r["parsed_content"],
                total_amount=float(r["total_amount"]),
                winning_amount=float(r["winning_amount"]),
                pnl_no_rebate=float(r["pnl_no_rebate"]),
                rebate_amount=float(r["rebate_amount"]),
                net_pnl=float(r["net_pnl"]),
                created_at=r["created_at"],
            )

    def add_order(self, order: OrderRecord) -> int:
        with self._db.connection() as conn:
            if order.seq_no <= 0:
                row = conn.execute(
                    "SELECT COALESCE(MAX(seq_no), 0) as max_seq FROM orders WHERE region = ?",
                    (order.region,),
                ).fetchone()
                order.seq_no = int(row["max_seq"]) + 1
            cur = conn.execute(
                """
                INSERT INTO orders(
                    seq_no, region, client_name, raw_text, parsed_content,
                    total_amount, winning_amount, pnl_no_rebate, rebate_amount, net_pnl, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.seq_no,
                    order.region,
                    order.client_name,
                    order.raw_text,
                    order.parsed_content,
                    round(order.total_amount, 2),
                    round(order.winning_amount, 2),
                    round(order.pnl_no_rebate, 2),
                    round(order.rebate_amount, 2),
                    round(order.net_pnl, 2),
                    order.created_at,
                ),
            )
            order.id = int(cur.lastrowid)
            return order.id

    def update_order_settlement(self, order: OrderRecord) -> None:
        if order.id is None:
            return
        with self._db.connection() as conn:
            conn.execute(
                """
                UPDATE orders
                SET winning_amount = ?, pnl_no_rebate = ?, rebate_amount = ?, net_pnl = ?
                WHERE id = ?
                """,
                (
                    round(order.winning_amount, 2),
                    round(order.pnl_no_rebate, 2),
                    round(order.rebate_amount, 2),
                    round(order.net_pnl, 2),
                    order.id,
                ),
            )

    def reset_region_settlement(self, region: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """
                UPDATE orders
                SET winning_amount = 0, pnl_no_rebate = 0, rebate_amount = 0, net_pnl = 0
                WHERE region = ?
                """,
                (region,),
            )

    def delete_order(self, order_id: int) -> None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT region FROM orders WHERE id = ?", (order_id,)).fetchone()
            conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            if row:
                region = row["region"]
                remaining = conn.execute(
                    "SELECT id FROM orders WHERE region = ? ORDER BY seq_no ASC, id ASC",
                    (region,),
                ).fetchall()
                for idx, r in enumerate(remaining, start=1):
                    conn.execute("UPDATE orders SET seq_no = ? WHERE id = ?", (idx, r["id"]))

    def clear_region_orders(self, region: str) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM orders WHERE region = ?", (region,))

    def list_orders_by_date_range(
        self,
        start_date: str,
        end_date: str,
        region: Optional[str] = None,
        client_filter: Optional[str] = None,
        keyword_filter: Optional[str] = None,
    ) -> List[OrderRecord]:
        """按日期范围 (YYYY-MM-DD ~ YYYY-MM-DD) 查询订单明细"""
        query = "SELECT * FROM orders WHERE substr(created_at, 1, 10) >= ? AND substr(created_at, 1, 10) <= ?"
        params: list = [start_date[:10], end_date[:10]]
        if region and region != "全部盘口":
            query += " AND region = ?"
            params.append(region)
        if client_filter and client_filter not in ("全部", "全部客户"):
            query += " AND client_name = ?"
            params.append(client_filter)
        if keyword_filter and keyword_filter.strip():
            kw = f"%{keyword_filter.strip()}%"
            query += " AND (raw_text LIKE ? OR parsed_content LIKE ? OR client_name LIKE ?)"
            params.extend([kw, kw, kw])
        query += " ORDER BY created_at ASC, seq_no ASC, id ASC"

        with self._db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                OrderRecord(
                    id=r["id"],
                    seq_no=int(r["seq_no"]),
                    region=r["region"],
                    client_name=r["client_name"],
                    raw_text=r["raw_text"],
                    parsed_content=r["parsed_content"],
                    total_amount=float(r["total_amount"]),
                    winning_amount=float(r["winning_amount"]),
                    pnl_no_rebate=float(r["pnl_no_rebate"]),
                    rebate_amount=float(r["rebate_amount"]),
                    net_pnl=float(r["net_pnl"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def list_distinct_order_dates(self, region: Optional[str] = None) -> List[str]:
        """获取所有存在订单记录的日期列表 (YYYY-MM-DD，按降序排列)"""
        query = "SELECT DISTINCT substr(created_at, 1, 10) as d FROM orders"
        params: list = []
        if region and region != "全部盘口":
            query += " WHERE region = ?"
            params.append(region)
        query += " ORDER BY d DESC"
        with self._db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [str(r["d"]) for r in rows if r["d"]]


class EatReportRepository(BaseRepository):
    """吃码上报状态与上庄管理仓储"""

    def get_eat_report_state(self, region: str) -> Dict[int, Tuple[float, float, float]]:
        """返回 {number: (eat_amount, report_amount, reported_amount)}"""
        state = {i: (0.0, 0.0, 0.0) for i in range(1, 50)}
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT number, eat_amount, report_amount, reported_amount FROM eat_report_state WHERE region = ?",
                (region,),
            ).fetchall()
            for r in rows:
                num = int(r["number"])
                if 1 <= num <= 49:
                    state[num] = (
                        round(float(r["eat_amount"]), 2),
                        round(float(r["report_amount"]), 2),
                        round(float(r["reported_amount"]), 2),
                    )
        return state

    def save_eat_report_state(self, region: str, state: Dict[int, Tuple[float, float, float]]) -> None:
        rows = [
            (region, num, round(vals[0], 2), round(vals[1], 2), round(vals[2], 2))
            for num, vals in state.items()
            if 1 <= num <= 49
        ]
        with self._db.connection() as conn:
            conn.executemany(
                """
                INSERT INTO eat_report_state(region, number, eat_amount, report_amount, reported_amount)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(region, number) DO UPDATE SET
                    eat_amount = excluded.eat_amount,
                    report_amount = excluded.report_amount,
                    reported_amount = excluded.reported_amount
                """,
                rows,
            )

    def clear_region_eat_state(self, region: str) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM eat_report_state WHERE region = ?", (region,))
            conn.execute(
                "UPDATE bookmakers SET report_text = '', reported_json = '{}', updated_at = '' WHERE region = ?",
                (region,),
            )

    def list_bookmakers(self, region: str) -> List[BookmakerRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM bookmakers WHERE region = ? ORDER BY id ASC",
                (region,),
            ).fetchall()
            result: List[BookmakerRecord] = []
            for r in rows:
                reported_map: Dict[int, float] = {}
                try:
                    raw = json.loads(r["reported_json"] or "{}")
                    for k, v in raw.items():
                        reported_map[int(k)] = float(v)
                except Exception:
                    pass
                result.append(
                    BookmakerRecord(
                        id=r["id"],
                        region=r["region"],
                        name=r["name"],
                        report_text=r["report_text"],
                        reported_map=reported_map,
                        updated_at=r["updated_at"],
                    )
                )
            return result

    def save_bookmaker(self, bm: BookmakerRecord) -> None:
        reported_json = json.dumps({str(k): round(v, 2) for k, v in bm.reported_map.items() if v != 0})
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO bookmakers(region, name, report_text, reported_json, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(region, name) DO UPDATE SET
                    report_text = excluded.report_text,
                    reported_json = excluded.reported_json,
                    updated_at = excluded.updated_at
                """,
                (bm.region, bm.name, bm.report_text, reported_json, bm.updated_at),
            )

    def rename_bookmaker(self, region: str, old_name: str, new_name: str) -> bool:
        new_name = new_name.strip()
        if not new_name:
            return False
        with self._db.connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM bookmakers WHERE region = ? AND name = ?",
                (region, new_name),
            ).fetchone()
            if exists:
                return False
            conn.execute(
                "UPDATE bookmakers SET name = ? WHERE region = ? AND name = ?",
                (new_name, region, old_name),
            )
        return True

    def save_snapshot(self, region: str, title: str, data_rows: List[Dict]) -> None:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._db.connection() as conn:
            conn.execute(
                "INSERT INTO eat_snapshots(region, title, snapshot_json, created_at) VALUES(?, ?, ?, ?)",
                (region, title, json.dumps(data_rows, ensure_ascii=False), now_str),
            )

    def list_snapshots(self, region: Optional[str] = None) -> List[Dict]:
        with self._db.connection() as conn:
            if region:
                rows = conn.execute(
                    "SELECT * FROM eat_snapshots WHERE region = ? ORDER BY id DESC",
                    (region,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM eat_snapshots ORDER BY id DESC").fetchall()
            return [
                {
                    "id": r["id"],
                    "region": r["region"],
                    "title": r["title"],
                    "data": json.loads(r["snapshot_json"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]


class KeywordRepository(BaseRepository):
    """智能识别关键字词库仓储（对应原 关键字列表 表）"""

    CATEGORIES = ("全部关键字", "关键字-各肖", "关键字-各号", "关键字-共")

    def get_keywords(self, category: str = "全部关键字") -> List[str]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT keyword FROM keywords WHERE category = ? ORDER BY length DESC, id ASC",
                (category,),
            ).fetchall()
            return [r["keyword"] for r in rows]

    def get_all_categories_map(self) -> Dict[str, List[str]]:
        return {cat: self.get_keywords(cat) for cat in self.CATEGORIES}

    def add_keyword(self, category: str, keyword: str) -> None:
        kw = keyword.strip()
        if not kw:
            return
        with self._db.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO keywords(category, keyword, length) VALUES(?, ?, ?)",
                (category, kw, len(kw)),
            )
            if category != "全部关键字":
                conn.execute(
                    "INSERT OR IGNORE INTO keywords(category, keyword, length) VALUES('全部关键字', ?, ?)",
                    (kw, len(kw)),
                )

    def delete_keyword(self, category: str, keyword: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "DELETE FROM keywords WHERE category = ? AND keyword = ?",
                (category, keyword),
            )

    def bulk_insert_keywords(self, cat_keywords: Dict[str, List[str]]) -> None:
        rows = []
        for cat, kw_list in cat_keywords.items():
            seen = set()
            for kw in kw_list:
                if kw and kw not in seen:
                    seen.add(kw)
                    rows.append((cat, kw, len(kw)))
        with self._db.connection() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO keywords(category, keyword, length) VALUES(?, ?, ?)",
                rows,
            )


class ReplaceRuleRepository(BaseRepository):
    """自定义文字替换规则仓储（对应原 文字替换 窗体）"""

    def list_rules(self, only_enabled: bool = False) -> List[ReplaceRule]:
        query = "SELECT * FROM replace_rules"
        if only_enabled:
            query += " WHERE is_enabled = 1"
        query += " ORDER BY LENGTH(find_text) DESC, id ASC"
        with self._db.connection() as conn:
            rows = conn.execute(query).fetchall()
            return [
                ReplaceRule(
                    id=r["id"],
                    find_text=r["find_text"],
                    replace_text=r["replace_text"],
                    is_enabled=bool(r["is_enabled"]),
                    description=r["description"],
                )
                for r in rows
            ]

    def save_rule(self, rule: ReplaceRule) -> None:
        if not rule.find_text:
            return
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO replace_rules(find_text, replace_text, is_enabled, description)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(find_text) DO UPDATE SET
                    replace_text = excluded.replace_text,
                    is_enabled = excluded.is_enabled,
                    description = excluded.description
                """,
                (rule.find_text, rule.replace_text, 1 if rule.is_enabled else 0, rule.description),
            )

    def delete_rule(self, rule_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM replace_rules WHERE id = ?", (rule_id,))


class HistoryArchiveRepository(BaseRepository):
    """每日/每期历史账目归档快照仓储（支持按日期查询、归档保存、删除及一键恢复）"""

    @staticmethod
    def _row_to_record(r) -> DailyArchiveRecord:
        return DailyArchiveRecord(
            id=int(r["id"]),
            archive_date=str(r["archive_date"]),
            region=str(r["region"]),
            title=str(r["title"]),
            winning_number=int(r["winning_number"]),
            base_zodiac=str(r["base_zodiac"]),
            total_bet=float(r["total_bet"]),
            total_winning=float(r["total_winning"]),
            total_rebate=float(r["total_rebate"]),
            net_pnl=float(r["net_pnl"]),
            order_count=int(r["order_count"]),
            client_count=int(r["client_count"]),
            orders_data=json.loads(r["orders_json"] or "[]"),
            settlements_data=json.loads(r["settlements_json"] or "[]"),
            risk_data=json.loads(r["risk_json"] or "[]"),
            created_at=str(r["created_at"]),
        )

    def save_archive(self, record: DailyArchiveRecord) -> int:
        with self._db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO daily_archives(
                    archive_date, region, title, winning_number, base_zodiac,
                    total_bet, total_winning, total_rebate, net_pnl,
                    order_count, client_count, orders_json, settlements_json, risk_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.archive_date[:10],
                    record.region,
                    record.title,
                    int(record.winning_number),
                    record.base_zodiac,
                    round(record.total_bet, 2),
                    round(record.total_winning, 2),
                    round(record.total_rebate, 2),
                    round(record.net_pnl, 2),
                    int(record.order_count),
                    int(record.client_count),
                    json.dumps(record.orders_data, ensure_ascii=False),
                    json.dumps(record.settlements_data, ensure_ascii=False),
                    json.dumps(record.risk_data, ensure_ascii=False),
                    record.created_at,
                ),
            )
            record.id = int(cur.lastrowid)
            return record.id

    def list_archives(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        region: Optional[str] = None,
    ) -> List[DailyArchiveRecord]:
        query = "SELECT * FROM daily_archives WHERE 1=1"
        params: list = []
        if start_date:
            query += " AND archive_date >= ?"
            params.append(start_date[:10])
        if end_date:
            query += " AND archive_date <= ?"
            params.append(end_date[:10])
        if region and region != "全部盘口":
            query += " AND region = ?"
            params.append(region)
        query += " ORDER BY archive_date DESC, id DESC"
        with self._db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_record(r) for r in rows]

    def get_archive_by_id(self, archive_id: int) -> Optional[DailyArchiveRecord]:
        with self._db.connection() as conn:
            r = conn.execute("SELECT * FROM daily_archives WHERE id = ?", (archive_id,)).fetchone()
            return self._row_to_record(r) if r else None

    def delete_archive(self, archive_id: int) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM daily_archives WHERE id = ?", (archive_id,))

    def list_distinct_archive_dates(self, region: Optional[str] = None) -> List[str]:
        query = "SELECT DISTINCT archive_date as d FROM daily_archives"
        params: list = []
        if region and region != "全部盘口":
            query += " WHERE region = ?"
            params.append(region)
        query += " ORDER BY d DESC"
        with self._db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [str(r["d"]) for r in rows if r["d"]]
