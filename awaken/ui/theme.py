"""Tema visual "System" (Solo Leveling): fundo azul-noite, painéis translúcidos com contorno luminoso."""

BG = "#050a14"          # fundo da janela
PANEL = "#0a1628"       # painéis
PANEL_ALT = "#0e1e36"   # elementos dentro dos painéis
BORDER = "#1f6fd1"      # contorno dos painéis
GLOW = "#4fc3ff"        # azul "System" (títulos, destaques)
TEXT = "#d6ecff"
TEXT_DIM = "#7f9bbd"
HP = "#ff4d6d"
XP = "#4fc3ff"
GOLD = "#f5c542"
SUCCESS = "#3ddc97"
DANGER = "#ff4d6d"

# cor de cada rank de dificuldade dos hábitos
HABIT_RANK_COLORS = {
    "E": "#8a9bb0", "D": "#3ddc97", "C": "#4fc3ff", "B": "#b07cff", "A": "#ff9f43", "S": "#ff4d6d",
}

# cor de cada ranking de cultivação
CULTIVATION_COLORS = {
    "Unranked": "#7f9bbd", "Bronze": "#cd7f32", "Silver": "#c0c7d1", "Gold": "#f5c542",
    "Dark Gold": "#b8860b", "Legend": "#ff9f43", "Heavenly Fate": "#4fc3ff", "Heavenly Star": "#7ee0ff",
    "Heavenly Axis": "#9d8cff", "Dao of Dragon": "#3ddc97", "Martial Ancestor": "#ff6b6b",
    "Deity": "#ffe08a", "Emperor": "#ff4dd2", "Supreme": "#ffffff",
}

FONT_FAMILY = "Segoe UI, DejaVu Sans, Arial"

STYLESHEET = f"""
* {{ font-family: {FONT_FAMILY}; color: {TEXT}; font-size: 13px; }}
QWidget {{ background: transparent; }}
/* depois da regra genérica: com a mesma especificidade, ganha a última */
QMainWindow, QDialog, QWidget#Page {{ background: {BG}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {BORDER}; border-radius: 3px;
                        background: {PANEL_ALT}; }}
QCheckBox::indicator:checked {{ background: {GLOW}; border-color: {GLOW}; }}

QFrame#Panel {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QLabel#PanelTitle {{
    color: {GLOW}; font-size: 15px; font-weight: bold; letter-spacing: 2px;
}}
QLabel#Dim {{ color: {TEXT_DIM}; }}
QLabel#Big {{ font-size: 22px; font-weight: bold; }}
QLabel#Gold {{ color: {GOLD}; font-weight: bold; }}

QListWidget#Sidebar {{
    background: {PANEL}; border: none; border-right: 1px solid {BORDER}; outline: none; padding-top: 8px;
}}
QListWidget#Sidebar::item {{ padding: 12px 18px; color: {TEXT_DIM}; }}
QListWidget#Sidebar::item:selected {{
    color: {GLOW}; background: {PANEL_ALT}; border-left: 3px solid {GLOW};
}}

QPushButton {{
    background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 12px;
}}
QPushButton:hover {{ border-color: {GLOW}; color: {GLOW}; }}
QPushButton:disabled {{ color: #3d5270; border-color: #1a3050; }}
QPushButton#Primary {{ background: #0f3a6e; border-color: {GLOW}; color: white; font-weight: bold; }}
QPushButton#Primary:disabled {{ background: {PANEL_ALT}; border-color: #1a3050; color: #3d5270; }}
QPushButton#Danger {{ border-color: {DANGER}; color: {DANGER}; }}
QPushButton#Small {{ padding: 2px 8px; min-width: 22px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: {PANEL}; color: {TEXT_DIM}; padding: 8px 18px; border: 1px solid {BORDER};
    border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px;
}}
QTabBar::tab:selected {{ color: {GLOW}; background: {PANEL_ALT}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 6px;
}}
QComboBox QAbstractItemView {{ background: {PANEL_ALT}; selection-background-color: #0f3a6e; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: {BG}; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {PANEL_ALT}; border: 1px solid {GLOW}; color: {TEXT}; }}
"""
