"""
全套卡通图标批量生成与视觉图鉴海报生成脚本 (scripts/generate_icons.py)
生成：
1. `src/assets/icons/*.svg` & `*.png` (共 38 个统一 Q 版 2.5D 卡通图标)
2. `src/assets/icons/app_icon.ico` & 根目录 `app_icon.ico` (含 16/32/48/64/128/256 多尺寸 Windows 图标)
3. `src/assets/icons/cartoon_icon_showcase.png` (全套卡通图标高清预览大图)
"""

from __future__ import annotations
import os
from pathlib import Path
import shutil
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt5.QtWidgets import QApplication
from src.ui.icon_manager import CartoonIconManager, get_icons_dir


ICON_LABELS = [
    ("app_icon", "主程序Icon (金马49)"),
    ("tab_dashboard", "主控风控看板"),
    ("tab_wechat", "微信智能收单"),
    ("tab_eat_risk", "吃码飞单护盾"),
    ("tab_settlement", "开奖对奖奖杯"),
    ("tab_history", "历史日期回看"),
    ("tab_settings", "系统参数设置"),
    ("tab_help", "使用说明宝典"),
    ("act_keyboard", "快捷键键盘"),
    ("act_update", "版本升级火箭"),
    ("kpi_pool", "全盘总收单袋"),
    ("kpi_client", "VIP客户押注"),
    ("kpi_risk", "头号高危预警"),
    ("kpi_profit", "红绿盈亏天平"),
    ("ball_red", "3D卡通红波球"),
    ("ball_blue", "3D卡通蓝波球"),
    ("ball_green", "3D卡通绿波球"),
    ("act_paste", "剪贴板粘贴"),
    ("act_parse", "放大镜识别"),
    ("act_add_order", "确认入库对勾"),
    ("act_edit", "修改修正铅笔"),
    ("act_negate", "一键负数冲抵"),
    ("act_clear", "小扫帚清空"),
    ("act_calculator", "二分反推计算器"),
    ("act_copy", "一键复制散码"),
    ("act_bookmaker", "上庄金库归档"),
    ("act_withdraw", "撤回上报箭头"),
    ("act_snapshot", "风控快照相机"),
    ("act_settle", "特码中奖靶心"),
    ("act_import_excel", "导入Excel表格"),
    ("act_export_excel", "导出Excel报表"),
    ("act_db_backup", "SQLite数据库"),
    ("act_delete", "撤单删除桶"),
    ("act_theme_dark", "暗夜月亮主题"),
    ("act_theme_light", "亮色太阳主题"),
    ("zodiac_鼠", "生肖·机灵鼠"),
    ("zodiac_牛", "生肖·勤恳牛"),
    ("zodiac_虎", "生肖·威风虎"),
    ("zodiac_兔", "生肖·招财兔"),
    ("zodiac_龙", "生肖·祥瑞龙"),
    ("zodiac_蛇", "生肖·灵巧蛇"),
    ("zodiac_马", "本命年·金马"),
    ("zodiac_羊", "生肖·福气羊"),
    ("zodiac_猴", "生肖·聪明猴"),
    ("zodiac_鸡", "生肖·金冠鸡"),
    ("zodiac_狗", "生肖·旺财狗"),
    ("zodiac_猪", "生肖·聚宝猪"),
]


def generate_showcase_poster(output_path: Path) -> None:
    """绘制全套 42 枚卡通风格图标的视觉图鉴总览海报"""
    cols = 6
    rows = (len(ICON_LABELS) + cols - 1) // cols
    cell_w = 190
    cell_h = 165
    margin_x = 36
    header_h = 95
    width = margin_x * 2 + cols * cell_w
    height = header_h + rows * cell_h + 36

    img = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("#F1F5F9"))

    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    font_fam = CartoonIconManager.ensure_fonts_loaded()

    # 顶部横幅
    painter.fillRect(0, 0, width, 76, QColor("#1E3A8A"))
    painter.setPen(QColor("#FFFFFF"))
    f_title = QFont(font_fam)
    f_title.setPixelSize(22)
    f_title.setBold(True)
    painter.setFont(f_title)
    painter.drawText(
        QRect(0, 8, width, 38),
        Qt.AlignCenter,
        "特码智能收单与风控系统 Pro — 全套 42 枚 Q 版卡通图标视觉规范图鉴",
    )
    painter.setPen(QColor("#FEF08A"))
    f_sub = QFont(font_fam)
    f_sub.setPixelSize(13)
    f_sub.setBold(True)
    painter.setFont(f_sub)
    painter.drawText(
        QRect(0, 44, width, 26),
        Qt.AlignCenter,
        "统一 2.5D 粗描边卡通风格 · 高辨识度视觉隐喻（一眼看懂每个功能与12生肖波色）",
    )

    for idx, (icon_key, label) in enumerate(ICON_LABELS):
        r = idx // cols
        c = idx % cols
        x = margin_x + c * cell_w
        y = header_h + r * cell_h

        # 白色圆角卡片背景
        card_rect = QRect(x + 8, y + 6, cell_w - 16, cell_h - 12)
        painter.setPen(QPen(QColor("#CBD5E1"), 2))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(card_rect, 14, 14)

        # 绘制卡通图标
        pm = CartoonIconManager.render_pixmap(icon_key, 88)
        icon_x = x + (cell_w - 88) // 2
        icon_y = y + 16
        painter.drawPixmap(icon_x, icon_y, pm)

        # 绘制中文名称与图标键名
        painter.setPen(QColor("#0F172A"))
        f_lbl = QFont(font_fam)
        f_lbl.setPixelSize(13)
        f_lbl.setBold(True)
        painter.setFont(f_lbl)
        painter.drawText(
            QRect(x + 10, y + 108, cell_w - 20, 24),
            Qt.AlignCenter,
            label,
        )
        painter.setPen(QColor("#64748B"))
        f_code = QFont(font_fam)
        f_code.setPixelSize(11)
        painter.setFont(f_code)
        painter.drawText(
            QRect(x + 10, y + 130, cell_w - 20, 18),
            Qt.AlignCenter,
            icon_key,
        )

    painter.end()
    img.save(str(output_path), "PNG")


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    icons_dir = get_icons_dir()
    exported = CartoonIconManager.export_all_assets(icons_dir)

    ico_src = icons_dir / "app_icon.ico"
    if ico_src.exists():
        shutil.copy2(ico_src, ROOT_DIR / "app_icon.ico")

    showcase_path = icons_dir / "cartoon_icon_showcase.png"
    generate_showcase_poster(showcase_path)
    print(f"Exported {len(exported)} cartoon icon assets to: {icons_dir}")
    print(f"Generated showcase poster: {showcase_path}")
    app.quit()


if __name__ == "__main__":
    main()
