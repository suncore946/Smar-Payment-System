"""
全套卡通风格图标生成与资源管理器 (CartoonIconManager)
采用统一的美式/国潮 Q 版 2.5D 卡通插画视觉规范：
- 统一粗描边 (#2B1810 / #1E293B)、圆润边角、高光质感与高饱和度明快色彩
- 纯矢量图形路径 + Windows 系统微软雅黑粗体字库显式加载，确保任何环境（含无头离屏 CI）100% 清晰无乱码
- 涵盖：主程序马年吉祥物特码 Icon (.ico/.png/.svg)、5大主工作台图标、5大设置子页图标、
  12生肖专属卡通萌宠头像（各自带标志性器官与头饰特征）、红蓝绿3色3D卡通波色球、以及核心功能按钮图标
"""

from __future__ import annotations
from pathlib import Path
import sys
from typing import Dict, Optional
from PyQt5.QtCore import QByteArray, QRectF, Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt5.QtSvg import QSvgRenderer


def get_icons_dir() -> Path:
    """获取图标资产目录路径（兼容源码环境与 PyInstaller 打包环境）"""
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / "src" / "assets" / "icons"
    return Path(__file__).resolve().parent.parent / "assets" / "icons"


class CartoonIconManager:
    """
    面向对象卡通图标管理器（单例缓存 + SVG 矢量高分屏无损渲染 + TrueType 字体徽章叠印）
    """

    _icon_cache: Dict[str, QIcon] = {}
    _pixmap_cache: Dict[str, QPixmap] = {}
    _fonts_loaded: bool = False
    _font_family: str = "Microsoft YaHei UI"

    @classmethod
    def ensure_fonts_loaded(cls) -> str:
        """显式注册系统字体文件，确保在 offscreen 无头模式或精简系统下汉字与数字 100% 完美渲染"""
        if cls._fonts_loaded:
            return cls._font_family
        cls._fonts_loaded = True
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        ]
        for fp in candidates:
            if Path(fp).exists():
                fid = QFontDatabase.addApplicationFont(fp)
                if fid != -1:
                    fams = QFontDatabase.applicationFontFamilies(fid)
                    if fams:
                        cls._font_family = fams[0]
                        break
        return cls._font_family

    # =========================================================================
    # 1. 核心应用与工作台纯矢量 SVG 卡通图案定义（128x128 视口，全部符号采用矢量路径）
    # =========================================================================
    SVG_TEMPLATES: Dict[str, str] = {
        # 主程序 Icon：Q版金马吉祥物 + 49号特码彩球 + 招财金元宝
        "app_icon": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <defs>
            <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#FF512F"/>
              <stop offset="55%" stop-color="#E11D48"/>
              <stop offset="100%" stop-color="#881337"/>
            </linearGradient>
            <linearGradient id="goldGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#FFF08A"/>
              <stop offset="50%" stop-color="#FACC15"/>
              <stop offset="100%" stop-color="#CA8A04"/>
            </linearGradient>
          </defs>
          <!-- 圆角喜庆红金底座 -->
          <rect x="5" y="5" width="118" height="118" rx="28" fill="url(#bgGrad)" stroke="#2B1810" stroke-width="5"/>
          <rect x="11" y="11" width="106" height="106" rx="22" fill="none" stroke="url(#goldGrad)" stroke-width="3" opacity="0.9"/>
          <path d="M 22 15 Q 64 25 106 15" fill="none" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round" opacity="0.45"/>
          <!-- 金马双耳与火红鬃毛 -->
          <path d="M 28 40 L 18 14 L 44 26 Z" fill="#FBBF24" stroke="#2B1810" stroke-width="4" stroke-linejoin="round"/>
          <path d="M 80 40 L 90 14 L 64 26 Z" fill="#FBBF24" stroke="#2B1810" stroke-width="4" stroke-linejoin="round"/>
          <path d="M 42 22 Q 54 6 68 22" fill="#EF4444" stroke="#2B1810" stroke-width="4" stroke-linecap="round"/>
          <!-- Q版小马头部与鼻子 -->
          <rect x="20" y="26" width="66" height="56" rx="26" fill="#FDE047" stroke="#2B1810" stroke-width="4.5"/>
          <!-- 额头白色流星斑 -->
          <path d="M 53 30 L 58 40 L 53 48 L 48 40 Z" fill="#FFFFFF"/>
          <rect x="27" y="52" width="52" height="30" rx="15" fill="#FEF9C3" stroke="#2B1810" stroke-width="3.5"/>
          <!-- 大眼睛与腮红 -->
          <circle cx="38" cy="43" r="5.5" fill="#2B1810"/>
          <circle cx="36" cy="41" r="2" fill="#FFFFFF"/>
          <circle cx="68" cy="43" r="5.5" fill="#2B1810"/>
          <circle cx="66" cy="41" r="2" fill="#FFFFFF"/>
          <ellipse cx="29" cy="50" rx="5" ry="3" fill="#FB7185"/>
          <ellipse cx="77" cy="50" rx="5" ry="3" fill="#FB7185"/>
          <!-- 鼻孔与大笑嘴型 -->
          <circle cx="43" cy="62" r="2.8" fill="#2B1810"/>
          <circle cx="63" cy="62" r="2.8" fill="#2B1810"/>
          <path d="M 44 71 Q 53 79 62 71" fill="none" stroke="#2B1810" stroke-width="3.5" stroke-linecap="round"/>
          <!-- 左下角：招财金元宝 -->
          <path d="M 12 94 Q 36 84 60 94 L 51 114 Q 36 118 21 114 Z" fill="url(#goldGrad)" stroke="#2B1810" stroke-width="4" stroke-linejoin="round"/>
          <ellipse cx="36" cy="92" rx="14" ry="6" fill="#FEF08A" stroke="#2B1810" stroke-width="3.5"/>
          <!-- 右下角：醒目 49 号特码蓝波球（纯矢量绘制数字 49） -->
          <circle cx="89" cy="87" r="30" fill="#2563EB" stroke="#2B1810" stroke-width="5"/>
          <path d="M 71 71 A 22 22 0 0 1 103 69" fill="none" stroke="#93C5FD" stroke-width="4" stroke-linecap="round"/>
          <circle cx="89" cy="87" r="20" fill="#FFFFFF" stroke="#2B1810" stroke-width="3.5"/>
          <!-- 纯矢量数字 "4" 与 "9" -->
          <path d="M 84 78 L 76 90 L 87 90 M 84 78 L 84 96" fill="none" stroke="#DC2626" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="95" cy="83" r="5" fill="none" stroke="#DC2626" stroke-width="4"/>
          <path d="M 100 83 L 100 92 Q 100 96 93 96" fill="none" stroke="#DC2626" stroke-width="4" stroke-linecap="round"/>
        </svg>
        """,

        # Tab 1: 主控看板与实时风控 (卡通雷达显示屏 + 柱状图 + 折线)
        "tab_dashboard": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="10" y="16" width="108" height="82" rx="18" fill="#3B82F6" stroke="#1E293B" stroke-width="5"/>
          <rect x="18" y="24" width="92" height="66" rx="12" fill="#EFF6FF" stroke="#1E293B" stroke-width="3.5"/>
          <path d="M 52 98 L 44 114 L 84 114 L 76 98 Z" fill="#94A3B8" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <rect x="34" y="110" width="60" height="8" rx="4" fill="#64748B" stroke="#1E293B" stroke-width="4"/>
          <rect x="28" y="58" width="16" height="24" rx="4" fill="#10B981" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="54" y="46" width="16" height="36" rx="4" fill="#F59E0B" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="80" y="34" width="16" height="48" rx="4" fill="#EF4444" stroke="#1E293B" stroke-width="3.5"/>
          <path d="M 32 48 L 58 36 L 86 28" fill="none" stroke="#2563EB" stroke-width="4.5" stroke-linecap="round"/>
          <circle cx="32" cy="48" r="5" fill="#FACC15" stroke="#1E293B" stroke-width="3"/>
          <circle cx="58" cy="36" r="5" fill="#FACC15" stroke="#1E293B" stroke-width="3"/>
          <circle cx="86" cy="28" r="5" fill="#FACC15" stroke="#1E293B" stroke-width="3"/>
        </svg>
        """,

        # Tab 2: 微信智能收单与极速录单 (Q版绿色微信双气泡 + 金色闪电)
        "tab_wechat": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <ellipse cx="78" cy="74" rx="38" ry="30" fill="#4ADE80" stroke="#1E293B" stroke-width="5"/>
          <path d="M 96 98 L 110 112 L 84 102 Z" fill="#4ADE80" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <ellipse cx="52" cy="52" rx="42" ry="34" fill="#22C55E" stroke="#1E293B" stroke-width="5"/>
          <path d="M 28 78 L 14 96 L 44 83 Z" fill="#22C55E" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <path d="M 24 34 Q 50 22 76 34" fill="none" stroke="#BBF7D0" stroke-width="4" stroke-linecap="round"/>
          <circle cx="38" cy="48" r="5.5" fill="#1E293B"/>
          <circle cx="66" cy="48" r="5.5" fill="#1E293B"/>
          <circle cx="36" cy="46" r="2" fill="#FFFFFF"/>
          <circle cx="64" cy="46" r="2" fill="#FFFFFF"/>
          <path d="M 44 60 Q 52 67 60 60" fill="none" stroke="#1E293B" stroke-width="3.5" stroke-linecap="round"/>
          <path d="M 90 12 L 66 52 L 86 52 L 70 96 L 110 44 L 88 44 Z" fill="#FACC15" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
        </svg>
        """,

        # Tab 3: 吃码上报与飞单风控 (卡通黄金蓝护盾 + 飞单纸飞机)
        "tab_eat_risk": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 64 10 L 110 28 L 110 62 C 110 92 64 116 64 116 C 64 116 18 92 18 62 L 18 28 Z"
                fill="#F59E0B" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <path d="M 64 20 L 98 34 L 98 60 C 98 84 64 104 64 104 C 64 104 30 84 30 60 L 30 34 Z"
                fill="#2563EB" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
          <path d="M 38 64 L 94 36 L 78 88 L 62 72 Z" fill="#FFFFFF" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
          <path d="M 94 36 L 62 72" stroke="#1E293B" stroke-width="3.5"/>
        </svg>
        """,

        # Tab 4: 订单明细与开奖算账 (卡通黄金奖杯 + 五角星勋章)
        "tab_settlement": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 30 30 C 10 30 10 62 34 64" fill="none" stroke="#F59E0B" stroke-width="10" stroke-linecap="round"/>
          <path d="M 30 30 C 10 30 10 62 34 64" fill="none" stroke="#1E293B" stroke-width="4" stroke-linecap="round"/>
          <path d="M 98 30 C 118 30 118 62 94 64" fill="none" stroke="#F59E0B" stroke-width="10" stroke-linecap="round"/>
          <path d="M 98 30 C 118 30 118 62 94 64" fill="none" stroke="#1E293B" stroke-width="4" stroke-linecap="round"/>
          <path d="M 30 18 L 98 18 L 90 66 C 86 84 42 84 38 66 Z" fill="#FACC15" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <rect x="54" y="78" width="20" height="18" fill="#F59E0B" stroke="#1E293B" stroke-width="4.5"/>
          <rect x="34" y="96" width="60" height="16" rx="6" fill="#EF4444" stroke="#1E293B" stroke-width="5"/>
          <!-- 杯身红色圆章与矢量五角星 -->
          <circle cx="64" cy="45" r="18" fill="#EF4444" stroke="#1E293B" stroke-width="4"/>
          <polygon points="64,31 68,40 78,40 70,46 73,55 64,50 55,55 58,46 50,40 60,40" fill="#FEF08A" stroke="#1E293B" stroke-width="2" stroke-linejoin="round"/>
        </svg>
        """,

        # Tab 5: 客户管理与自定义配置 (卡通大齿轮 + 红色扳手)
        "tab_settings": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="52" y="10" width="16" height="18" rx="4" fill="#60A5FA" stroke="#1E293B" stroke-width="4.5"/>
          <rect x="52" y="100" width="16" height="18" rx="4" fill="#60A5FA" stroke="#1E293B" stroke-width="4.5"/>
          <rect x="6" y="56" width="18" height="16" rx="4" fill="#60A5FA" stroke="#1E293B" stroke-width="4.5"/>
          <rect x="96" y="56" width="18" height="16" rx="4" fill="#60A5FA" stroke="#1E293B" stroke-width="4.5"/>
          <circle cx="60" cy="64" r="38" fill="#60A5FA" stroke="#1E293B" stroke-width="5"/>
          <circle cx="60" cy="64" r="16" fill="#EFF6FF" stroke="#1E293B" stroke-width="4.5"/>
          <path d="M 74 74 L 110 110 L 118 102 L 82 66 Z" fill="#F87171" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <circle cx="74" cy="70" r="14" fill="#EF4444" stroke="#1E293B" stroke-width="4.5"/>
          <circle cx="74" cy="70" r="5" fill="#FEF2F2"/>
        </svg>
        """,

        # KPI 1: 全盘总收单 (招财钱袋 + 矢量人民币符号 ¥)
        "kpi_pool": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 42 24 L 86 24 L 74 42 L 54 42 Z" fill="#FACC15" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <path d="M 50 40 C 18 50 14 106 40 112 L 88 112 C 114 106 110 50 78 40 Z" fill="#F59E0B" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <rect x="46" y="36" width="36" height="8" rx="4" fill="#EF4444" stroke="#1E293B" stroke-width="3.5"/>
          <circle cx="64" cy="78" r="23" fill="#FEF08A" stroke="#1E293B" stroke-width="4"/>
          <!-- 矢量 ¥ 符号 -->
          <path d="M 55 66 L 64 76 L 73 66 M 64 76 L 64 92 M 55 78 L 73 78 M 55 85 L 73 85" fill="none" stroke="#B45309" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """,

        # KPI 2: 当前客户总额 (Q版皇冠VIP客户头像)
        "kpi_client": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 22 112 C 22 76 106 76 106 112 Z" fill="#3B82F6" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <circle cx="64" cy="54" r="24" fill="#FDE68A" stroke="#1E293B" stroke-width="5"/>
          <path d="M 42 34 L 48 14 L 64 24 L 80 14 L 86 34 Z" fill="#FACC15" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
          <circle cx="56" cy="52" r="3.5" fill="#1E293B"/>
          <circle cx="72" cy="52" r="3.5" fill="#1E293B"/>
          <path d="M 56 62 Q 64 68 72 62" fill="none" stroke="#1E293B" stroke-width="3.5" stroke-linecap="round"/>
        </svg>
        """,

        # KPI 3: 头号风险预警 (卡通红色三角警示牌)
        "kpi_risk": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 64 14 L 114 106 L 14 106 Z" fill="#EF4444" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <path d="M 64 30 L 100 96 L 28 96 Z" fill="#FEF2F2" stroke="#1E293B" stroke-width="3.5" stroke-linejoin="round"/>
          <rect x="58" y="46" width="12" height="26" rx="6" fill="#DC2626" stroke="#1E293B" stroke-width="3"/>
          <circle cx="64" cy="84" r="6.5" fill="#DC2626" stroke="#1E293B" stroke-width="3"/>
        </svg>
        """,

        # KPI 4: 盈余/亏损号数统计 (卡通红绿双勋章 + 矢量正负号)
        "kpi_profit": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="44" cy="60" r="32" fill="#10B981" stroke="#1E293B" stroke-width="5"/>
          <path d="M 44 46 L 44 74 M 30 60 L 58 60" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>
          <circle cx="86" cy="70" r="30" fill="#F43F5E" stroke="#1E293B" stroke-width="5"/>
          <path d="M 72 70 L 100 70" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>
        </svg>
        """,

        # 3D 卡通红波球
        "ball_red": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="52" fill="#EF4444" stroke="#1E293B" stroke-width="6"/>
          <path d="M 32 36 A 38 38 0 0 1 88 28" fill="none" stroke="#FCA5A5" stroke-width="7" stroke-linecap="round"/>
          <circle cx="64" cy="64" r="26" fill="#FFFFFF" stroke="#1E293B" stroke-width="4.5"/>
          <circle cx="64" cy="64" r="12" fill="#EF4444"/>
        </svg>
        """,

        # 3D 卡通蓝波球
        "ball_blue": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="52" fill="#3B82F6" stroke="#1E293B" stroke-width="6"/>
          <path d="M 32 36 A 38 38 0 0 1 88 28" fill="none" stroke="#93C5FD" stroke-width="7" stroke-linecap="round"/>
          <circle cx="64" cy="64" r="26" fill="#FFFFFF" stroke="#1E293B" stroke-width="4.5"/>
          <circle cx="64" cy="64" r="12" fill="#3B82F6"/>
        </svg>
        """,

        # 3D 卡通绿波球
        "ball_green": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="52" fill="#10B981" stroke="#1E293B" stroke-width="6"/>
          <path d="M 32 36 A 38 38 0 0 1 88 28" fill="none" stroke="#6EE7B7" stroke-width="7" stroke-linecap="round"/>
          <circle cx="64" cy="64" r="26" fill="#FFFFFF" stroke="#1E293B" stroke-width="4.5"/>
          <circle cx="64" cy="64" r="12" fill="#10B981"/>
        </svg>
        """,

        # 操作按钮：粘贴并识别 (卡通写字板)
        "act_paste": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="24" y="22" width="80" height="92" rx="14" fill="#F59E0B" stroke="#1E293B" stroke-width="5"/>
          <rect x="34" y="34" width="60" height="70" rx="8" fill="#FFFFFF" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="44" y="12" width="40" height="18" rx="6" fill="#94A3B8" stroke="#1E293B" stroke-width="4.5"/>
          <line x1="44" y1="52" x2="84" y2="52" stroke="#3B82F6" stroke-width="5" stroke-linecap="round"/>
          <line x1="44" y1="68" x2="84" y2="68" stroke="#3B82F6" stroke-width="5" stroke-linecap="round"/>
          <line x1="44" y1="84" x2="68" y2="84" stroke="#3B82F6" stroke-width="5" stroke-linecap="round"/>
        </svg>
        """,

        # 操作按钮：立即识别 (卡通放大镜)
        "act_parse": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <line x1="78" y1="78" x2="112" y2="112" stroke="#F59E0B" stroke-width="16" stroke-linecap="round"/>
          <line x1="78" y1="78" x2="112" y2="112" stroke="#1E293B" stroke-width="5" stroke-linecap="round"/>
          <circle cx="54" cy="54" r="36" fill="#60A5FA" stroke="#1E293B" stroke-width="5"/>
          <circle cx="54" cy="54" r="24" fill="#EFF6FF" stroke="#1E293B" stroke-width="3.5"/>
          <path d="M 42 42 Q 54 32 66 42" fill="none" stroke="#93C5FD" stroke-width="4" stroke-linecap="round"/>
        </svg>
        """,

        # 操作按钮：确认添加入库 (卡通绿色对勾勋章)
        "act_add_order": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="50" fill="#10B981" stroke="#1E293B" stroke-width="5.5"/>
          <path d="M 40 66 L 56 84 L 90 46" fill="none" stroke="#FFFFFF" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """,

        # 操作按钮：一键负数冲抵 (卡通橙红减号反转牌)
        "act_negate": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="50" fill="#F97316" stroke="#1E293B" stroke-width="5.5"/>
          <rect x="34" y="54" width="60" height="20" rx="10" fill="#FFFFFF" stroke="#1E293B" stroke-width="4"/>
        </svg>
        """,

        # 操作按钮：清空/重置 (卡通橡皮擦)
        "act_clear": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 88 18 L 110 40 L 54 96 L 20 96 L 20 74 Z" fill="#F472B6" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <path d="M 42 62 L 66 86 L 54 96 L 20 96 L 20 74 Z" fill="#FBCFE8" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
          <line x1="20" y1="110" x2="108" y2="110" stroke="#94A3B8" stroke-width="6" stroke-linecap="round"/>
        </svg>
        """,

        # 操作按钮：智能二分计算器 (卡通计算器)
        "act_calculator": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="24" y="12" width="80" height="104" rx="16" fill="#3B82F6" stroke="#1E293B" stroke-width="5"/>
          <rect x="36" y="24" width="56" height="24" rx="6" fill="#DCFCE7" stroke="#1E293B" stroke-width="3.5"/>
          <circle cx="44" cy="66" r="7" fill="#FACC15" stroke="#1E293B" stroke-width="3"/>
          <circle cx="64" cy="66" r="7" fill="#FACC15" stroke="#1E293B" stroke-width="3"/>
          <circle cx="84" cy="66" r="7" fill="#FACC15" stroke="#1E293B" stroke-width="3"/>
          <circle cx="44" cy="90" r="7" fill="#FFFFFF" stroke="#1E293B" stroke-width="3"/>
          <circle cx="64" cy="90" r="7" fill="#FFFFFF" stroke="#1E293B" stroke-width="3"/>
          <circle cx="84" cy="90" r="7" fill="#EF4444" stroke="#1E293B" stroke-width="3"/>
        </svg>
        """,

        # 操作按钮：复制散码 (卡通双页文档)
        "act_copy": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="40" y="16" width="66" height="80" rx="12" fill="#93C5FD" stroke="#1E293B" stroke-width="4.5"/>
          <rect x="22" y="32" width="66" height="80" rx="12" fill="#FFFFFF" stroke="#1E293B" stroke-width="5"/>
          <line x1="36" y1="54" x2="74" y2="54" stroke="#2563EB" stroke-width="5" stroke-linecap="round"/>
          <line x1="36" y1="72" x2="74" y2="72" stroke="#2563EB" stroke-width="5" stroke-linecap="round"/>
          <line x1="36" y1="90" x2="58" y2="90" stroke="#2563EB" stroke-width="5" stroke-linecap="round"/>
        </svg>
        """,

        # 操作按钮：上庄金库保存 (卡通银行金库)
        "act_bookmaker": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 64 14 L 114 42 L 14 42 Z" fill="#FACC15" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <rect x="22" y="42" width="84" height="56" fill="#E2E8F0" stroke="#1E293B" stroke-width="4.5"/>
          <rect x="32" y="48" width="12" height="44" fill="#94A3B8" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="58" y="48" width="12" height="44" fill="#94A3B8" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="84" y="48" width="12" height="44" fill="#94A3B8" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="14" y="98" width="100" height="14" rx="5" fill="#64748B" stroke="#1E293B" stroke-width="4.5"/>
        </svg>
        """,

        # 操作按钮：撤回上报 (卡通回旋箭头)
        "act_withdraw": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="50" fill="#FEF3C7" stroke="#1E293B" stroke-width="5"/>
          <path d="M 54 32 L 26 56 L 54 80 L 54 64 C 78 64 88 76 88 94 C 100 72 94 44 54 44 Z"
                fill="#D97706" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
        </svg>
        """,

        # 操作按钮：风控快照相机 (卡通相机)
        "act_snapshot": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 42 26 L 52 14 L 76 14 L 86 26 Z" fill="#60A5FA" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <rect x="14" y="26" width="100" height="78" rx="18" fill="#3B82F6" stroke="#1E293B" stroke-width="5"/>
          <circle cx="64" cy="65" r="24" fill="#EFF6FF" stroke="#1E293B" stroke-width="4.5"/>
          <circle cx="64" cy="65" r="12" fill="#2563EB"/>
          <circle cx="94" cy="42" r="6" fill="#FACC15" stroke="#1E293B" stroke-width="3"/>
        </svg>
        """,

        # 操作按钮：立即对奖算账 (卡通红心靶盘+金箭)
        "act_settle": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="60" cy="68" r="46" fill="#EF4444" stroke="#1E293B" stroke-width="5"/>
          <circle cx="60" cy="68" r="30" fill="#FFFFFF" stroke="#1E293B" stroke-width="4"/>
          <circle cx="60" cy="68" r="14" fill="#EF4444" stroke="#1E293B" stroke-width="3.5"/>
          <line x1="60" y1="68" x2="108" y2="20" stroke="#FACC15" stroke-width="8" stroke-linecap="round"/>
          <line x1="60" y1="68" x2="108" y2="20" stroke="#1E293B" stroke-width="3" stroke-linecap="round"/>
        </svg>
        """,

        # 操作按钮：导入 Excel (卡通绿色电子表格网格 + 矢量 X + 向下箭头)
        "act_import_excel": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="16" y="14" width="78" height="96" rx="12" fill="#10B981" stroke="#1E293B" stroke-width="5"/>
          <rect x="28" y="28" width="54" height="64" rx="6" fill="#D1FAE5" stroke="#1E293B" stroke-width="3"/>
          <!-- 矢量 X 标志 -->
          <path d="M 40 42 L 68 78 M 68 42 L 40 78" stroke="#047857" stroke-width="8" stroke-linecap="round"/>
          <circle cx="94" cy="88" r="26" fill="#FACC15" stroke="#1E293B" stroke-width="4.5"/>
          <path d="M 94 74 L 94 100 M 82 88 L 94 100 L 106 88" fill="none" stroke="#1E293B" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """,

        # 操作按钮：导出 Excel (卡通绿色电子表格网格 + 矢量 X + 向上箭头)
        "act_export_excel": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="16" y="14" width="78" height="96" rx="12" fill="#059669" stroke="#1E293B" stroke-width="5"/>
          <rect x="28" y="28" width="54" height="64" rx="6" fill="#ECFDF5" stroke="#1E293B" stroke-width="3"/>
          <path d="M 40 42 L 68 78 M 68 42 L 40 78" stroke="#065F46" stroke-width="8" stroke-linecap="round"/>
          <circle cx="94" cy="88" r="26" fill="#38BDF8" stroke="#1E293B" stroke-width="4.5"/>
          <path d="M 94 102 L 94 76 M 82 88 L 94 76 L 106 88" fill="none" stroke="#1E293B" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """,

        # 操作按钮：暗色主题 (卡通弯月+星星)
        "act_theme_dark": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 78 18 C 44 22 24 56 36 88 C 48 114 84 116 104 94 C 76 98 56 76 62 46 C 64 34 70 24 78 18 Z"
                fill="#FACC15" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <circle cx="94" cy="36" r="6" fill="#FEF08A" stroke="#1E293B" stroke-width="3"/>
          <circle cx="108" cy="58" r="4" fill="#FEF08A" stroke="#1E293B" stroke-width="2.5"/>
        </svg>
        """,

        # 操作按钮：亮色主题 (卡通笑脸小太阳)
        "act_theme_light": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="32" fill="#FACC15" stroke="#1E293B" stroke-width="5"/>
          <line x1="64" y1="10" x2="64" y2="22" stroke="#F59E0B" stroke-width="7" stroke-linecap="round"/>
          <line x1="64" y1="106" x2="64" y2="118" stroke="#F59E0B" stroke-width="7" stroke-linecap="round"/>
          <line x1="10" y1="64" x2="22" y2="64" stroke="#F59E0B" stroke-width="7" stroke-linecap="round"/>
          <line x1="106" y1="64" x2="118" y2="64" stroke="#F59E0B" stroke-width="7" stroke-linecap="round"/>
          <line x1="25" y1="25" x2="34" y2="34" stroke="#F59E0B" stroke-width="7" stroke-linecap="round"/>
          <line x1="94" y1="94" x2="103" y2="103" stroke="#F59E0B" stroke-width="7" stroke-linecap="round"/>
          <line x1="103" y1="25" x2="94" y2="34" stroke="#F59E0B" stroke-width="7" stroke-linecap="round"/>
          <line x1="34" y1="94" x2="25" y2="103" stroke="#F59E0B" stroke-width="7" stroke-linecap="round"/>
        </svg>
        """,

        # 操作按钮：删除/撤单 (卡通红色垃圾桶)
        "act_delete": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="24" y="24" width="80" height="14" rx="6" fill="#EF4444" stroke="#1E293B" stroke-width="4.5"/>
          <rect x="48" y="12" width="32" height="12" rx="4" fill="#FCA5A5" stroke="#1E293B" stroke-width="4"/>
          <path d="M 32 38 L 96 38 L 90 112 L 38 112 Z" fill="#F87171" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <line x1="52" y1="54" x2="52" y2="96" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>
          <line x1="76" y1="54" x2="76" y2="96" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>
        </svg>
        """,

        # 操作按钮：数据库备份 (卡通圆柱数据库)
        "act_db_backup": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <path d="M 24 32 L 24 96 C 24 110 104 110 104 96 L 104 32 Z" fill="#3B82F6" stroke="#1E293B" stroke-width="5"/>
          <ellipse cx="64" cy="32" rx="40" ry="14" fill="#93C5FD" stroke="#1E293B" stroke-width="5"/>
          <path d="M 24 54 C 24 68 104 68 104 54" fill="none" stroke="#1E293B" stroke-width="4.5"/>
          <path d="M 24 76 C 24 90 104 90 104 76" fill="none" stroke="#1E293B" stroke-width="4.5"/>
        </svg>
        """,

        # 操作按钮：新增 (卡通绿底加号勋章)
        "act_plus": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r="48" fill="#22C55E" stroke="#1E293B" stroke-width="5"/>
          <line x1="64" y1="36" x2="64" y2="92" stroke="#FFFFFF" stroke-width="11" stroke-linecap="round"/>
          <line x1="36" y1="64" x2="92" y2="64" stroke="#FFFFFF" stroke-width="11" stroke-linecap="round"/>
        </svg>
        """,

        # 导航6 / 帮助按钮：使用说明与指南 (卡通翻开魔法指南书 + 金色书签 + 灯泡问号勋章)
        "tab_help": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <!-- 书本精装外皮 -->
          <rect x="10" y="24" width="108" height="84" rx="12" fill="#2563EB" stroke="#1E293B" stroke-width="5"/>
          <!-- 左右书页 -->
          <path d="M 18 20 Q 41 16 64 26 L 64 98 Q 41 88 18 94 Z" fill="#FFFBEB" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <path d="M 110 20 Q 87 16 64 26 L 64 98 Q 87 88 110 94 Z" fill="#FEF3C7" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <!-- 书页文字条纹 -->
          <line x1="27" y1="40" x2="53" y2="43" stroke="#64748B" stroke-width="4" stroke-linecap="round"/>
          <line x1="27" y1="54" x2="53" y2="57" stroke="#64748B" stroke-width="4" stroke-linecap="round"/>
          <line x1="27" y1="68" x2="46" y2="70" stroke="#64748B" stroke-width="4" stroke-linecap="round"/>
          <line x1="75" y1="43" x2="101" y2="40" stroke="#64748B" stroke-width="4" stroke-linecap="round"/>
          <line x1="75" y1="57" x2="101" y2="54" stroke="#64748B" stroke-width="4" stroke-linecap="round"/>
          <!-- 红色丝带书签 -->
          <path d="M 58 96 L 58 118 L 64 111 L 70 118 L 70 96 Z" fill="#EF4444" stroke="#1E293B" stroke-width="3.5" stroke-linejoin="round"/>
          <!-- 右下角：金色问号勋章 -->
          <circle cx="94" cy="86" r="24" fill="#FACC15" stroke="#1E293B" stroke-width="4.5"/>
          <path d="M 87 77 C 87 69 101 69 101 78 C 101 83 94 84 94 90" fill="none" stroke="#1E293B" stroke-width="5" stroke-linecap="round"/>
          <circle cx="94" cy="99" r="3.2" fill="#1E293B"/>
        </svg>
        """,

        # 操作：修改/修正客户名 — 卡通铅笔 + 名片便签
        "act_edit": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <!-- 底部白色名片/便签纸 -->
          <rect x="20" y="28" width="76" height="82" rx="12" fill="#FFFFFF" stroke="#1E293B" stroke-width="4.5"/>
          <path d="M 28 44 L 64 44" stroke="#CBD5E1" stroke-width="4" stroke-linecap="round"/>
          <path d="M 28 60 L 76 60" stroke="#CBD5E1" stroke-width="4" stroke-linecap="round"/>
          <path d="M 28 76 L 56 76" stroke="#CBD5E1" stroke-width="4" stroke-linecap="round"/>
          <!-- 斜放的卡通黄色铅笔 -->
          <g transform="translate(68, 20) rotate(42)">
            <!-- 笔身 -->
            <rect x="-10" y="0" width="20" height="66" rx="4" fill="#FACC15" stroke="#1E293B" stroke-width="4"/>
            <!-- 笔尾粉色橡皮擦 -->
            <rect x="-10" y="-12" width="20" height="14" rx="3" fill="#F472B6" stroke="#1E293B" stroke-width="4"/>
            <rect x="-10" y="-3" width="20" height="5" fill="#94A3B8" stroke="#1E293B" stroke-width="2"/>
            <!-- 笔尖与笔芯 -->
            <polygon points="-10,66 10,66 0,84" fill="#FEF08A" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
            <polygon points="-4,77 4,77 0,84" fill="#1E293B"/>
          </g>
        </svg>
        """,

        # 设置子页 / 快捷键：卡通多彩机械键盘 + 金色闪电
        "act_keyboard": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <!-- 顶部键盘连接线 -->
          <path d="M 64 34 Q 64 16 82 14" fill="none" stroke="#475569" stroke-width="5" stroke-linecap="round"/>
          <!-- 键盘外壳 -->
          <rect x="8" y="34" width="112" height="74" rx="16" fill="#E2E8F0" stroke="#1E293B" stroke-width="5"/>
          <rect x="14" y="40" width="100" height="60" rx="11" fill="#CBD5E1"/>
          <!-- 第一排多彩键帽 -->
          <rect x="20" y="46" width="18" height="16" rx="4" fill="#EF4444" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="44" y="46" width="18" height="16" rx="4" fill="#FFFFFF" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="68" y="46" width="18" height="16" rx="4" fill="#FFFFFF" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="92" y="46" width="16" height="16" rx="4" fill="#3B82F6" stroke="#1E293B" stroke-width="3.5"/>
          <!-- 第二排键帽与橙色回车键 -->
          <rect x="20" y="68" width="22" height="14" rx="4" fill="#FACC15" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="48" y="68" width="18" height="14" rx="4" fill="#FFFFFF" stroke="#1E293B" stroke-width="3.5"/>
          <rect x="72" y="68" width="36" height="14" rx="4" fill="#22C55E" stroke="#1E293B" stroke-width="3.5"/>
          <!-- 底部大空格键 -->
          <rect x="34" y="86" width="60" height="10" rx="4" fill="#FFFFFF" stroke="#1E293B" stroke-width="3.5"/>
          <!-- 右上角快捷键闪电徽章 -->
          <polygon points="104,8 86,34 99,34 93,56 116,28 102,28" fill="#FACC15" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
        </svg>
        """,

        # 版本管理与自动更新：卡通升空小火箭 + 云端向上箭头
        "act_update": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <!-- 底部云朵底座 -->
          <path d="M 18 108 C 10 108 8 94 20 92 C 24 80 42 82 48 90 C 56 80 76 80 84 90 C 94 82 110 86 110 98 C 118 100 116 112 104 112 Z" fill="#E0F2FE" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <!-- 火箭尾焰 -->
          <path d="M 52 84 L 64 114 L 76 84 Z" fill="#F97316" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
          <path d="M 57 84 L 64 102 L 71 84 Z" fill="#FEF08A"/>
          <!-- 左右推进尾翼 -->
          <path d="M 44 62 L 24 84 L 46 82 Z" fill="#EF4444" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <path d="M 84 62 L 104 84 L 82 82 Z" fill="#EF4444" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <!-- 火箭主体与红色整流罩 -->
          <path d="M 64 10 C 44 28 42 56 46 84 L 82 84 C 86 56 84 28 64 10 Z" fill="#FFFFFF" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <path d="M 64 10 C 54 20 49 32 47 40 L 81 40 C 79 32 74 20 64 10 Z" fill="#EF4444" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
          <!-- 蓝色舷窗 -->
          <circle cx="64" cy="58" r="12" fill="#38BDF8" stroke="#1E293B" stroke-width="4.5"/>
          <circle cx="60" cy="54" r="3.5" fill="#FFFFFF"/>
        </svg>
        """,

        # 导航：按日期历史回看 (卡通红头日历本 + 右下角时光回溯金钟表)
        "tab_history": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <!-- 日历白底主体 -->
          <rect x="12" y="20" width="92" height="88" rx="16" fill="#FFFFFF" stroke="#1E293B" stroke-width="5"/>
          <!-- 日历红色顶栏 -->
          <path d="M 12 36 C 12 24 20 20 28 20 L 88 20 C 96 20 104 24 104 36 L 104 46 L 12 46 Z" fill="#EF4444" stroke="#1E293B" stroke-width="5" stroke-linejoin="round"/>
          <!-- 顶部两个金属挂环 -->
          <rect x="30" y="10" width="12" height="22" rx="6" fill="#FACC15" stroke="#1E293B" stroke-width="4"/>
          <rect x="74" y="10" width="12" height="22" rx="6" fill="#FACC15" stroke="#1E293B" stroke-width="4"/>
          <!-- 日历内部日期色块网格 -->
          <rect x="24" y="56" width="16" height="14" rx="3" fill="#93C5FD" stroke="#1E293B" stroke-width="3"/>
          <rect x="48" y="56" width="16" height="14" rx="3" fill="#22C55E" stroke="#1E293B" stroke-width="3"/>
          <rect x="72" y="56" width="16" height="14" rx="3" fill="#FDE047" stroke="#1E293B" stroke-width="3"/>
          <rect x="24" y="78" width="16" height="14" rx="3" fill="#FCA5A5" stroke="#1E293B" stroke-width="3"/>
          <rect x="48" y="78" width="16" height="14" rx="3" fill="#93C5FD" stroke="#1E293B" stroke-width="3"/>
          <!-- 右下角：时光回看金色怀表 -->
          <circle cx="92" cy="90" r="28" fill="#FACC15" stroke="#1E293B" stroke-width="5"/>
          <circle cx="92" cy="90" r="20" fill="#FFFBEB" stroke="#1E293B" stroke-width="3.5"/>
          <!-- 时钟指针 -->
          <polyline points="92,76 92,90 102,96" fill="none" stroke="#DC2626" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="92" cy="90" r="3.5" fill="#1E293B"/>
        </svg>
        """,
    }

    # =========================================================================
    # 2. 12 生肖专属 Q 版萌宠头像生成器（每个动物拥有独一无二的耳朵/角/鼻子/胡须特征）
    # =========================================================================
    ZODIAC_PALETTE: Dict[str, tuple[str, str, str]] = {
        "鼠": ("#CBD5E1", "#F472B6", "#334155"),
        "牛": ("#D97706", "#FDE047", "#78350F"),
        "虎": ("#FB923C", "#FEF08A", "#C2410C"),
        "兔": ("#FFFFFF", "#FDA4AF", "#E11D48"),
        "龙": ("#FACC15", "#EF4444", "#B45309"),
        "蛇": ("#4ADE80", "#FEF08A", "#15803D"),
        "马": ("#FBBF24", "#EF4444", "#B91C1C"),
        "羊": ("#FEF3C7", "#D97706", "#92400E"),
        "猴": ("#D97706", "#FDE68A", "#78350F"),
        "鸡": ("#FEF08A", "#EF4444", "#DC2626"),
        "狗": ("#FDBA74", "#9A3412", "#7C2D12"),
        "猪": ("#FBCFE8", "#F472B6", "#BE185D"),
    }

    @classmethod
    def get_zodiac_svg(cls, zodiac: str) -> str:
        """为每个生肖生成高辨识度的专属 Q 版动物特征 SVG"""
        face_col, acc_col, badge_col = cls.ZODIAC_PALETTE.get(
            zodiac, ("#FDE047", "#EF4444", "#1D4ED8")
        )
        ears = ""
        extra_face = ""

        if zodiac == "鼠":
            ears = f"""
            <circle cx="30" cy="28" r="18" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
            <circle cx="30" cy="28" r="10" fill="{acc_col}"/>
            <circle cx="98" cy="28" r="18" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
            <circle cx="98" cy="28" r="10" fill="{acc_col}"/>
            """
            extra_face = """
            <circle cx="64" cy="64" r="4.5" fill="#E11D48"/>
            <path d="M 24 58 L 42 62 M 22 68 L 42 68 M 104 58 L 86 62 M 106 68 L 86 68" stroke="#1E293B" stroke-width="3" stroke-linecap="round"/>
            """
        elif zodiac == "牛":
            ears = f"""
            <path d="M 32 38 Q 14 14 38 14 Q 44 24 46 32 Z" fill="{acc_col}" stroke="#1E293B" stroke-width="4.5"/>
            <path d="M 96 38 Q 114 14 90 14 Q 84 24 82 32 Z" fill="{acc_col}" stroke="#1E293B" stroke-width="4.5"/>
            """
            extra_face = """
            <ellipse cx="64" cy="68" rx="18" ry="11" fill="#FDE68A" stroke="#1E293B" stroke-width="3.5"/>
            <circle cx="64" cy="76" r="6" fill="none" stroke="#FACC15" stroke-width="3.5"/>
            """
        elif zodiac == "虎":
            ears = f"""
            <circle cx="34" cy="28" r="14" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
            <circle cx="94" cy="28" r="14" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
            """
            extra_face = """
            <path d="M 52 34 L 76 34 M 56 41 L 72 41 M 64 28 L 64 46" stroke="#1E293B" stroke-width="4" stroke-linecap="round"/>
            """
        elif zodiac == "兔":
            ears = f"""
            <ellipse cx="44" cy="22" rx="10" ry="22" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
            <ellipse cx="44" cy="22" rx="5" ry="14" fill="{acc_col}"/>
            <ellipse cx="84" cy="22" rx="10" ry="22" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
            <ellipse cx="84" cy="22" rx="5" ry="14" fill="{acc_col}"/>
            """
            extra_face = """
            <polygon points="64,66 60,61 68,61" fill="#FB7185"/>
            """
        elif zodiac == "龙":
            ears = f"""
            <path d="M 38 34 L 22 10 L 36 18 L 42 8 L 48 30 Z" fill="#EF4444" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
            <path d="M 90 34 L 106 10 L 92 18 L 86 8 L 80 30 Z" fill="#EF4444" stroke="#1E293B" stroke-width="4" stroke-linejoin="round"/>
            """
            extra_face = """
            <ellipse cx="64" cy="66" rx="16" ry="10" fill="#FEF08A" stroke="#1E293B" stroke-width="3.5"/>
            """
        elif zodiac == "蛇":
            ears = """
            <path d="M 52 28 L 58 14 L 64 22 L 70 14 L 76 28 Z" fill="#FACC15" stroke="#1E293B" stroke-width="3.5" stroke-linejoin="round"/>
            """
            extra_face = """
            <path d="M 64 76 L 64 90 L 59 95 M 64 90 L 69 95" fill="none" stroke="#EF4444" stroke-width="3.5" stroke-linecap="round"/>
            """
        elif zodiac == "马":
            ears = f"""
            <path d="M 36 36 L 26 12 L 48 26 Z" fill="{face_col}" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
            <path d="M 92 36 L 102 12 L 80 26 Z" fill="{face_col}" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
            <path d="M 48 24 Q 64 8 80 24" fill="#EF4444" stroke="#1E293B" stroke-width="4"/>
            """
            extra_face = """
            <polygon points="64,34 68,43 64,51 60,43" fill="#FFFFFF"/>
            """
        elif zodiac == "羊":
            ears = f"""
            <path d="M 34 36 C 14 20 18 48 34 46" fill="{acc_col}" stroke="#1E293B" stroke-width="4.5"/>
            <path d="M 94 36 C 114 20 110 48 94 46" fill="{acc_col}" stroke="#1E293B" stroke-width="4.5"/>
            <circle cx="52" cy="28" r="10" fill="#FFFFFF" stroke="#1E293B" stroke-width="3.5"/>
            <circle cx="64" cy="25" r="11" fill="#FFFFFF" stroke="#1E293B" stroke-width="3.5"/>
            <circle cx="76" cy="28" r="10" fill="#FFFFFF" stroke="#1E293B" stroke-width="3.5"/>
            """
        elif zodiac == "猴":
            ears = f"""
            <circle cx="24" cy="58" r="14" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
            <circle cx="24" cy="58" r="7" fill="{acc_col}"/>
            <circle cx="104" cy="58" r="14" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
            <circle cx="104" cy="58" r="7" fill="{acc_col}"/>
            """
            extra_face = f"""
            <ellipse cx="64" cy="64" rx="26" ry="20" fill="{acc_col}"/>
            """
        elif zodiac == "鸡":
            ears = f"""
            <path d="M 48 28 Q 54 6 64 20 Q 74 6 80 28 Z" fill="{acc_col}" stroke="#1E293B" stroke-width="4.5"/>
            """
            extra_face = """
            <polygon points="64,74 56,62 72,62" fill="#F97316" stroke="#1E293B" stroke-width="3" stroke-linejoin="round"/>
            """
        elif zodiac == "狗":
            ears = f"""
            <ellipse cx="28" cy="52" rx="11" ry="22" transform="rotate(15 28 52)" fill="{acc_col}" stroke="#1E293B" stroke-width="4.5"/>
            <ellipse cx="100" cy="52" rx="11" ry="22" transform="rotate(-15 100 52)" fill="{acc_col}" stroke="#1E293B" stroke-width="4.5"/>
            """
            extra_face = """
            <circle cx="64" cy="63" r="5.5" fill="#1E293B"/>
            """
        elif zodiac == "猪":
            ears = f"""
            <path d="M 32 36 L 20 16 L 46 26 Z" fill="{face_col}" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
            <path d="M 96 36 L 108 16 L 82 26 Z" fill="{face_col}" stroke="#1E293B" stroke-width="4.5" stroke-linejoin="round"/>
            """
            extra_face = f"""
            <ellipse cx="64" cy="65" rx="14" ry="9" fill="{acc_col}" stroke="#1E293B" stroke-width="3.5"/>
            <circle cx="59" cy="65" r="2.5" fill="#1E293B"/>
            <circle cx="69" cy="65" r="2.5" fill="#1E293B"/>
            """

        return f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
          <rect x="6" y="6" width="116" height="116" rx="28" fill="#F8FAFC" stroke="{badge_col}" stroke-width="5"/>
          {ears}
          <ellipse cx="64" cy="62" rx="38" ry="34" fill="{face_col}" stroke="#1E293B" stroke-width="4.5"/>
          {extra_face}
          <circle cx="48" cy="54" r="5.5" fill="#1E293B"/>
          <circle cx="46" cy="52" r="2" fill="#FFFFFF"/>
          <circle cx="80" cy="54" r="5.5" fill="#1E293B"/>
          <circle cx="78" cy="52" r="2" fill="#FFFFFF"/>
          <ellipse cx="36" cy="62" rx="6" ry="3.5" fill="#FB7185"/>
          <ellipse cx="92" cy="62" rx="6" ry="3.5" fill="#FB7185"/>
          <path d="M 56 74 Q 64 81 72 74" fill="none" stroke="#1E293B" stroke-width="3.5" stroke-linecap="round"/>
          <rect x="74" y="78" width="42" height="38" rx="12" fill="{badge_col}" stroke="#1E293B" stroke-width="3.5"/>
        </svg>
        """

    @classmethod
    def get_svg_content(cls, name: str) -> str:
        """获取指定图标名称的 SVG 源码"""
        if name.startswith("zodiac_"):
            zod = name.split("_", 1)[1]
            return cls.get_zodiac_svg(zod)
        return cls.SVG_TEMPLATES.get(name, cls.SVG_TEMPLATES["app_icon"])

    @classmethod
    def render_pixmap(cls, name: str, size: int = 64) -> QPixmap:
        """
        将卡通图标渲染为指定像素尺寸的高清抗锯齿 QPixmap：
        优先加载打包内置的预渲染高清 PNG（文字与矢量已固化为像素，完全不依赖目标机器字库），
        若本地 PNG 不存在则实时通过 SVG + 系统字体渲染。
        """
        cache_key = f"{name}:{size}"
        if cache_key in cls._pixmap_cache:
            return cls._pixmap_cache[cache_key]

        png_file = get_icons_dir() / f"{name}.png"
        if png_file.exists():
            pm = QPixmap(str(png_file))
            if not pm.isNull():
                if pm.width() != size or pm.height() != size:
                    pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                cls._pixmap_cache[cache_key] = pm
                return pm

        font_fam = cls.ensure_fonts_loaded()
        svg_str = cls.get_svg_content(name)
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        renderer.render(painter, QRectF(0, 0, size, size))

        # 为 12 生肖图标右下角铭牌叠印清晰汉字
        if name.startswith("zodiac_"):
            zod = name.split("_", 1)[1]
            scale = size / 128.0
            badge_rect = QRectF(74 * scale, 78 * scale, 42 * scale, 38 * scale)
            painter.setPen(QColor("#FFFFFF"))
            font = QFont(font_fam)
            font.setPixelSize(max(10, int(22 * scale)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(badge_rect, Qt.AlignCenter, zod)

        painter.end()

        pixmap = QPixmap.fromImage(image)
        cls._pixmap_cache[cache_key] = pixmap
        return pixmap

    @classmethod
    def get_icon(cls, name: str, size: int = 64) -> QIcon:
        """获取带多尺寸适配的 QIcon 实例"""
        if name in cls._icon_cache:
            return cls._icon_cache[name]

        icon = QIcon()
        for sz in (24, 32, 48, 64, 128):
            icon.addPixmap(cls.render_pixmap(name, sz))
        cls._icon_cache[name] = icon
        return icon

    @classmethod
    def export_all_assets(cls, output_dir: Optional[Path] = None) -> Dict[str, Path]:
        """将全套卡通风格图标批量导出为 `.svg`、`.png` 及 Windows 多尺寸 `.ico` 文件"""
        cls._pixmap_cache.clear()
        cls._icon_cache.clear()
        target_dir = output_dir or get_icons_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        exported: Dict[str, Path] = {}

        all_names = list(cls.SVG_TEMPLATES.keys()) + [
            f"zodiac_{z}" for z in ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
        ]

        for name in all_names:
            svg_code = cls.get_svg_content(name).strip()
            svg_path = target_dir / f"{name}.svg"
            svg_path.write_text(svg_code, encoding="utf-8")

            png_path = target_dir / f"{name}.png"
            if png_path.exists():
                png_path.unlink()
            pm = cls.render_pixmap(name, 256 if name == "app_icon" else 128)
            pm.save(str(png_path), "PNG")
            exported[name] = png_path

        try:
            from PIL import Image

            app_png = target_dir / "app_icon.png"
            ico_path = target_dir / "app_icon.ico"
            with Image.open(app_png) as img:
                img.save(
                    str(ico_path),
                    format="ICO",
                    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
                )
            exported["app_icon.ico"] = ico_path
        except Exception:
            pass

        return exported
