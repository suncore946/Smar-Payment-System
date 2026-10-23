"""
系统全局版本管理元数据与语义化版本比较器 (src/version.py)
集中管理当前软件版本号、构建日期、更新通道及历次版本更新日志 (Changelog)
"""

from __future__ import annotations
from dataclasses import dataclass
import re
from typing import List, Tuple

APP_NAME = "特码智能收单风控系统Pro"
APP_VERSION = "2.1.0"
APP_BUILD_DATE = "2026-10-23"
APP_CHANNEL = "stable"

# 官方唯一指定更新源仓库（系统全局写死锁定，严防第三方篡改）
OFFICIAL_GITHUB_REPO = "suncore946/Smar-Payment-System"
OFFICIAL_UPDATE_API_URL = f"https://api.github.com/repos/{OFFICIAL_GITHUB_REPO}/releases/latest"
OFFICIAL_RAW_VERSION_URL = f"https://raw.githubusercontent.com/{OFFICIAL_GITHUB_REPO}/main/version.json"

DEFAULT_UPDATE_SOURCE_MODE = "github_api"
DEFAULT_UPDATE_URL = OFFICIAL_GITHUB_REPO


@dataclass(frozen=True)
class ChangelogEntry:
    """单次版本发布日志结构"""
    version: str
    release_date: str
    highlights: Tuple[str, ...]


CHANGELOG_HISTORY: Tuple[ChangelogEntry, ...] = (
    ChangelogEntry(
        version="2.1.0",
        release_date="2026-10-23",
        highlights=(
            "新增双模版本管理与自动更新引擎（支持 GitHub/Gitee Releases 免费托管与自定义服务器 version.json）",
            "支持 SHA256 完整性校验、后台静默检查更新、Windows 单文件 .exe 无缝自替换升级与词库热更新",
            "新增「使用说明与快捷键指南」工作台（含新手 5 步教程、14 类微信口语语法表与 4 组一键试玩案例）",
            "新增 20 项全局与工作台可自定义快捷键系统（支持按键冲突检测与一键恢复默认）",
            "遵循 Windows 标准规范将用户数据库默认存放至 %LOCALAPPDATA%\\LotteryRiskPro\\data，升级 .exe 永不丢数据",
        ),
    ),
    ChangelogEntry(
        version="2.0.0",
        release_date="2026-10-23",
        highlights=(
            "全新设计并内嵌 44 枚统一 2.5D 粗描边 Q 版卡通图标体系（金马 49 特码主图标、12 生肖专属头像、3D 波色球）",
            "完成对原版 Excel 宏工作簿 29 笔真实历史订单的 100% 零误差解析验证与本地 SQLite WAL 数据库重构",
            "内置设定最大允许亏损二分法自动反推最佳单号吃码上限与多上庄飞单归档撤回系统",
        ),
    ),
)


def parse_version_tuple(version_str: str) -> Tuple[int, ...]:
    """
    将版本号字符串（如 'v2.1.0'、'2.1.0-beta1'）解析为整数元组 (2, 1, 0) 以便精确比较大小
    """
    cleaned = (version_str or "").strip().lstrip("vV")
    nums = [int(x) for x in re.findall(r"\d+", cleaned)]
    if not nums:
        return (0, 0, 0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:4])


def is_newer_version(remote_version: str, current_version: str = APP_VERSION) -> bool:
    """判断远端版本号是否高于当前本地版本号"""
    return parse_version_tuple(remote_version) > parse_version_tuple(current_version)
