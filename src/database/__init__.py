"""
数据持久化与仓储层 (Database & Repository Layer)
基于 SQLite 与面向对象仓储模式 (Repository Pattern) 实现本地持久化
"""

from .db_manager import DatabaseManager
from .repositories import (
    ConfigRepository,
    RegionRepository,
    ClientRepository,
    OrderRepository,
    EatReportRepository,
    KeywordRepository,
    ReplaceRuleRepository,
)

__all__ = [
    "DatabaseManager",
    "ConfigRepository",
    "RegionRepository",
    "ClientRepository",
    "OrderRepository",
    "EatReportRepository",
    "KeywordRepository",
    "ReplaceRuleRepository",
]
