"""
本地 SQLite 数据库管理器 (DatabaseManager)
封装数据库连接、事务管理、表结构迁移与自动备份功能
"""

from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Generator, Optional

APP_DATA_FOLDER_NAME = "LotteryRiskPro"


def get_default_user_data_dir() -> Path:
    """
    获取符合操作系统规范的当前用户应用数据目录（绝不污染 .exe 所在目录或桌面）：
    - Windows: %LOCALAPPDATA%\\LotteryRiskPro\\data （例如 C:\\Users\\<用户名>\\AppData\\Local\\LotteryRiskPro\\data）
    - macOS: ~/Library/Application Support/LotteryRiskPro/data
    - Linux: ~/.local/share/LotteryRiskPro/data
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else (Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        root = Path(xdg) if xdg else (Path.home() / ".local" / "share")

    data_dir = root / APP_DATA_FOLDER_NAME / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_default_db_path() -> Path:
    """获取默认的用户数据本地 SQLite 数据库完整路径"""
    return get_default_user_data_dir() / "lottery_system.db"


class DatabaseManager:
    """面向对象本地 SQLite 数据库管理器"""

    def __init__(self, db_path: str | Path) -> None:
        self._is_memory = str(db_path) == ":memory:"
        self.db_path = Path(db_path) if not self._is_memory else Path(":memory:")
        self._mem_conn: Optional[sqlite3.Connection] = None
        if not self._is_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        try:
            self._init_schema()
        except sqlite3.DatabaseError:
            # 自愈保护：若本地数据库文件损坏或非合法 SQLite 文件，自动备份损坏文件并重建全新数据库
            if not self._is_memory and self.db_path.exists():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                bad_backup = self.db_path.with_name(f"{self.db_path.stem}_corrupted_{ts}.bak")
                try:
                    shutil.move(str(self.db_path), str(bad_backup))
                except Exception:
                    try:
                        self.db_path.unlink()
                    except Exception:
                        pass
                self._init_schema()
            else:
                raise

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        if self._is_memory and self._mem_conn is not None:
            try:
                yield self._mem_conn
                self._mem_conn.commit()
            except Exception:
                self._mem_conn.rollback()
                raise
            return

        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS regions (
                    name TEXT PRIMARY KEY,
                    display_order INTEGER NOT NULL DEFAULT 1,
                    global_odds REAL NOT NULL DEFAULT 47.0,
                    global_rebate REAL NOT NULL DEFAULT 0.02,
                    active_client_name TEXT NOT NULL DEFAULT '',
                    last_winning_number INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region TEXT NOT NULL,
                    name TEXT NOT NULL,
                    odds REAL NOT NULL DEFAULT 47.0,
                    rebate REAL NOT NULL DEFAULT 0.0,
                    sort_order INTEGER NOT NULL DEFAULT 1,
                    bets_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(region, name)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seq_no INTEGER NOT NULL,
                    region TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    parsed_content TEXT NOT NULL,
                    total_amount REAL NOT NULL DEFAULT 0.0,
                    winning_amount REAL NOT NULL DEFAULT 0.0,
                    pnl_no_rebate REAL NOT NULL DEFAULT 0.0,
                    rebate_amount REAL NOT NULL DEFAULT 0.0,
                    net_pnl REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_orders_region_client ON orders(region, client_name);
                CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);

                CREATE TABLE IF NOT EXISTS daily_archives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_date TEXT NOT NULL,
                    region TEXT NOT NULL,
                    title TEXT NOT NULL,
                    winning_number INTEGER NOT NULL DEFAULT 0,
                    base_zodiac TEXT NOT NULL DEFAULT '马',
                    total_bet REAL NOT NULL DEFAULT 0.0,
                    total_winning REAL NOT NULL DEFAULT 0.0,
                    total_rebate REAL NOT NULL DEFAULT 0.0,
                    net_pnl REAL NOT NULL DEFAULT 0.0,
                    order_count INTEGER NOT NULL DEFAULT 0,
                    client_count INTEGER NOT NULL DEFAULT 0,
                    orders_json TEXT NOT NULL DEFAULT '[]',
                    settlements_json TEXT NOT NULL DEFAULT '[]',
                    risk_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_daily_archives_date_region ON daily_archives(archive_date, region);

                CREATE TABLE IF NOT EXISTS eat_report_state (
                    region TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    eat_amount REAL NOT NULL DEFAULT 0.0,
                    report_amount REAL NOT NULL DEFAULT 0.0,
                    reported_amount REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (region, number)
                );

                CREATE TABLE IF NOT EXISTS bookmakers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region TEXT NOT NULL,
                    name TEXT NOT NULL,
                    report_text TEXT NOT NULL DEFAULT '',
                    reported_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT '',
                    UNIQUE(region, name)
                );

                CREATE TABLE IF NOT EXISTS eat_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region TEXT NOT NULL,
                    title TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    length INTEGER NOT NULL,
                    UNIQUE(category, keyword)
                );
                CREATE INDEX IF NOT EXISTS idx_keywords_cat_len ON keywords(category, length DESC);

                CREATE TABLE IF NOT EXISTS replace_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    find_text TEXT NOT NULL UNIQUE,
                    replace_text TEXT NOT NULL,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    description TEXT NOT NULL DEFAULT ''
                );
                """
            )

    def is_initialized_with_seed_data(self) -> bool:
        """检查数据库是否已经初始化过默认地区与关键字数据"""
        with self.connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM regions").fetchone()
            kw_row = conn.execute("SELECT COUNT(*) as cnt FROM keywords").fetchone()
            return bool(row and row["cnt"] > 0 and kw_row and kw_row["cnt"] > 0)

    def backup_database(self, backup_dir: Optional[str | Path] = None) -> Path:
        """一键备份当前本地 SQLite 数据库文件"""
        if backup_dir is None:
            target_dir = self.db_path.parent / "backups"
        else:
            target_dir = Path(backup_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = target_dir / f"lottery_db_backup_{ts}.db"
        with self.connection() as conn:
            bck = sqlite3.connect(str(dest))
            with bck:
                conn.backup(bck)
            bck.close()
        return dest

    def restore_database(self, backup_file: str | Path) -> None:
        """从备份文件恢复数据库"""
        src = Path(backup_file)
        if not src.exists():
            raise FileNotFoundError(f"备份文件不存在: {src}")
        src_conn = sqlite3.connect(str(src))
        with self.connection() as dest_conn:
            src_conn.backup(dest_conn)
        src_conn.close()

    def backup_to(self, dest_file: str | Path) -> Path:
        """将当前 SQLite 数据库直接备份至指定文件路径"""
        dest = Path(dest_file)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            bck = sqlite3.connect(str(dest))
            with bck:
                conn.backup(bck)
            bck.close()
        return dest

    def restore_from(self, src_file: str | Path) -> None:
        """从指定备份文件路径恢复数据库"""
        self.restore_database(src_file)
