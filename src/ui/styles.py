"""
现代化主题与样式管理器 (ThemeManager)
提供高颜值亮色 (Light) 与暗色 (Dark) 桌面主题样式表 (QSS)，以及波色与盈亏色彩工具函数
"""

from __future__ import annotations
from PyQt5.QtGui import QColor


class ThemeManager:
    """面向对象 UI 主题样式管理器"""

    WAVE_COLORS = {
        "red": ("#EF4444", "#FEE2E2", "#991B1B"),    # (主色, 浅底色, 深字色)
        "blue": ("#3B82F6", "#DBEAFE", "#1E40AF"),
        "green": ("#10B981", "#D1FAE5", "#065F46"),
    }

    @classmethod
    def get_wave_bg_fg(cls, wave: str, dark_mode: bool = False) -> tuple[QColor, QColor]:
        if wave == "red":
            return (QColor("#7F1D1D"), QColor("#FCA5A5")) if dark_mode else (QColor("#FEE2E2"), QColor("#B91C1C"))
        if wave == "blue":
            return (QColor("#1E3A8A"), QColor("#93C5FD")) if dark_mode else (QColor("#DBEAFE"), QColor("#1D4ED8"))
        return (QColor("#064E3B"), QColor("#6EE7B7")) if dark_mode else (QColor("#D1FAE5"), QColor("#047857"))

    @classmethod
    def get_wave_color_hex(cls, wave: str, dark_mode: bool = False) -> str:
        _, fg = cls.get_wave_bg_fg(wave, dark_mode)
        return fg.name()

    @classmethod
    def get_wave_bg_hex(cls, wave: str, dark_mode: bool = False) -> str:
        bg, _ = cls.get_wave_bg_fg(wave, dark_mode)
        return bg.name()

    @classmethod
    def get_pnl_color(cls, value: float, dark_mode: bool = False) -> QColor:
        if value < 0:
            return QColor("#F87171") if dark_mode else QColor("#DC2626")
        if value > 0:
            return QColor("#34D399") if dark_mode else QColor("#16A34A")
        return QColor("#94A3B8") if dark_mode else QColor("#64748B")

    @classmethod
    def get_pnl_color_hex(cls, value: float, dark_mode: bool = False) -> str:
        return cls.get_pnl_color(value, dark_mode).name()

    @classmethod
    def get_stylesheet(cls, theme: str = "light") -> str:
        if theme == "dark":
            return cls._dark_qss()
        return cls._light_qss()

    @staticmethod
    def _light_qss() -> str:
        return """
        QMainWindow, QDialog {
            background-color: #F1F5F9;
            color: #0F172A;
            font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            font-size: 13px;
        }
        QWidget {
            font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            font-size: 13px;
            color: #1E293B;
        }
        /* Top Bar */
        QFrame#TopHeaderBar {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E3A8A, stop:0.5 #1D4ED8, stop:1 #2563EB);
            border-bottom: 1px solid #1E40AF;
            padding: 6px 12px;
        }
        QFrame#TopHeaderBar QLabel {
            color: #FFFFFF;
        }
        QLabel#AppTitleLabel {
            font-size: 17px;
            font-weight: bold;
            color: #FFFFFF;
        }
        QLabel#HeaderBadge {
            background-color: rgba(255, 255, 255, 0.18);
            color: #FEF08A;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 6px;
            padding: 3px 8px;
            font-weight: bold;
            font-size: 12px;
        }
        /* Card Containers */
        QFrame#CardFrame, QFrame[card="true"], QGroupBox {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
        }
        QLabel[sectionTitle="true"] {
            font-size: 14px;
            font-weight: bold;
            color: #1E40AF;
        }
        QGroupBox {
            margin-top: 10px;
            padding-top: 16px;
            font-weight: bold;
            color: #0F172A;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 6px;
            color: #1E40AF;
            font-size: 13px;
            font-weight: bold;
        }
        /* KPI Metric Cards */
        QFrame#KpiCard {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left: 4px solid #2563EB;
            border-radius: 8px;
            padding: 6px 10px;
        }
        QFrame#KpiCardDanger {
            background-color: #FFF1F2;
            border: 1px solid #FECDD3;
            border-left: 4px solid #E11D48;
            border-radius: 8px;
            padding: 6px 10px;
        }
        QFrame#KpiCardSuccess {
            background-color: #ECFDF5;
            border: 1px solid #A7F3D0;
            border-left: 4px solid #059669;
            border-radius: 8px;
            padding: 6px 10px;
        }
        /* Tabs */
        QTabWidget::pane {
            border: 1px solid #CBD5E1;
            background: #F8FAFC;
            border-radius: 8px;
            top: -1px;
        }
        QTabBar::tab {
            background: #E2E8F0;
            color: #475569;
            padding: 9px 20px;
            margin-right: 4px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: bold;
            font-size: 13px;
        }
        QTabBar::tab:hover {
            background: #CBD5E1;
            color: #0F172A;
        }
        QTabBar::tab:selected {
            background: #FFFFFF;
            color: #1D4ED8;
            border-top: 3px solid #2563EB;
        }
        /* Buttons */
        QPushButton {
            background-color: #2563EB;
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: bold;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #1D4ED8;
        }
        QPushButton:pressed {
            background-color: #1E40AF;
        }
        QPushButton:disabled {
            background-color: #94A3B8;
            color: #E2E8F0;
        }
        QPushButton#SuccessBtn, QPushButton[success="true"] {
            background-color: #059669;
        }
        QPushButton#SuccessBtn:hover, QPushButton[success="true"]:hover {
            background-color: #047857;
        }
        QPushButton#DangerBtn, QPushButton[danger="true"] {
            background-color: #DC2626;
        }
        QPushButton#DangerBtn:hover, QPushButton[danger="true"]:hover {
            background-color: #B91C1C;
        }
        QPushButton#SecondaryBtn {
            background-color: #F1F5F9;
            color: #334155;
            border: 1px solid #CBD5E1;
        }
        QPushButton#SecondaryBtn:hover {
            background-color: #E2E8F0;
            color: #0F172A;
        }
        QPushButton#WarningBtn, QPushButton[warning="true"] {
            background-color: #D97706;
            color: #FFFFFF;
        }
        QPushButton#WarningBtn:hover, QPushButton[warning="true"]:hover {
            background-color: #B45309;
        }
        QPushButton#TagChipBtn {
            background-color: #F8FAFC;
            color: #334155;
            border: 1px solid #CBD5E1;
            border-radius: 5px;
            padding: 4px 8px;
            font-weight: bold;
        }
        QPushButton#TagChipBtn:checked {
            background-color: #2563EB;
            color: #FFFFFF;
            border: 1px solid #1D4ED8;
        }
        /* Inputs */
        QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #FFFFFF;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 5px 8px;
            selection-background-color: #2563EB;
            selection-color: #FFFFFF;
        }
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border: 1.5px solid #2563EB;
        }
        /* Tables */
        QTableWidget {
            background-color: #FFFFFF;
            alternate-background-color: #F8FAFC;
            gridline-color: #E2E8F0;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            selection-background-color: #DBEAFE;
            selection-color: #1E3A8A;
        }
        QHeaderView::section {
            background-color: #F1F5F9;
            color: #334155;
            font-weight: bold;
            padding: 6px 6px;
            border: none;
            border-right: 1px solid #E2E8F0;
            border-bottom: 2px solid #CBD5E1;
        }
        QScrollBar:vertical {
            background: #F1F5F9;
            width: 10px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical {
            background: #94A3B8;
            min-height: 24px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #64748B;
        }
        """

    @staticmethod
    def _dark_qss() -> str:
        return """
        QMainWindow, QDialog {
            background-color: #0F172A;
            color: #F8FAFC;
            font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            font-size: 13px;
        }
        QWidget {
            font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            font-size: 13px;
            color: #E2E8F0;
        }
        QFrame#TopHeaderBar {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0F172A, stop:0.5 #1E293B, stop:1 #1E3A8A);
            border-bottom: 1px solid #334155;
            padding: 6px 12px;
        }
        QLabel#AppTitleLabel {
            font-size: 17px;
            font-weight: bold;
            color: #F8FAFC;
        }
        QLabel#HeaderBadge {
            background-color: rgba(59, 130, 246, 0.25);
            color: #FDE047;
            border: 1px solid #3B82F6;
            border-radius: 6px;
            padding: 3px 8px;
            font-weight: bold;
        }
        QFrame#CardFrame, QFrame[card="true"], QGroupBox {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 10px;
        }
        QLabel[sectionTitle="true"] {
            font-size: 14px;
            font-weight: bold;
            color: #60A5FA;
        }
        QGroupBox {
            margin-top: 10px;
            padding-top: 16px;
            font-weight: bold;
            color: #F8FAFC;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 6px;
            color: #60A5FA;
            font-size: 13px;
            font-weight: bold;
        }
        QFrame#KpiCard {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-left: 4px solid #3B82F6;
            border-radius: 8px;
            padding: 6px 10px;
        }
        QFrame#KpiCardDanger {
            background-color: #31101C;
            border: 1px solid #881337;
            border-left: 4px solid #F43F5E;
            border-radius: 8px;
            padding: 6px 10px;
        }
        QFrame#KpiCardSuccess {
            background-color: #062E22;
            border: 1px solid #065F46;
            border-left: 4px solid #10B981;
            border-radius: 8px;
            padding: 6px 10px;
        }
        QTabWidget::pane {
            border: 1px solid #334155;
            background: #0F172A;
            border-radius: 8px;
            top: -1px;
        }
        QTabBar::tab {
            background: #1E293B;
            color: #94A3B8;
            padding: 9px 20px;
            margin-right: 4px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: bold;
        }
        QTabBar::tab:selected {
            background: #334155;
            color: #60A5FA;
            border-top: 3px solid #3B82F6;
        }
        QPushButton {
            background-color: #2563EB;
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #3B82F6;
        }
        QPushButton#SuccessBtn, QPushButton[success="true"] {
            background-color: #059669;
        }
        QPushButton#DangerBtn, QPushButton[danger="true"] {
            background-color: #DC2626;
        }
        QPushButton#SecondaryBtn {
            background-color: #334155;
            color: #E2E8F0;
            border: 1px solid #475569;
        }
        QPushButton#WarningBtn, QPushButton[warning="true"] {
            background-color: #D97706;
        }
        QPushButton#TagChipBtn {
            background-color: #1E293B;
            color: #CBD5E1;
            border: 1px solid #475569;
            border-radius: 5px;
            padding: 4px 8px;
            font-weight: bold;
        }
        QPushButton#TagChipBtn:checked {
            background-color: #2563EB;
            color: #FFFFFF;
            border: 1px solid #60A5FA;
        }
        QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #0F172A;
            color: #F8FAFC;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 5px 8px;
        }
        QTableWidget {
            background-color: #1E293B;
            alternate-background-color: #0F172A;
            gridline-color: #334155;
            border: 1px solid #334155;
            border-radius: 8px;
            selection-background-color: #1E3A8A;
            selection-color: #FFFFFF;
        }
        QHeaderView::section {
            background-color: #0F172A;
            color: #CBD5E1;
            font-weight: bold;
            padding: 6px 6px;
            border: none;
            border-right: 1px solid #334155;
            border-bottom: 2px solid #475569;
        }
        """
