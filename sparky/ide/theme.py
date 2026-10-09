# Sparky IDE styling (Spark 3). One Qt stylesheet built from a palette of
# design tokens (design.py). LIGHT/DARK stay as names for older code.

import os

from PyQt6.QtGui import QFontDatabase

from .design import CODE_FONTS, HEADING_FONTS, UI_FONTS, complete, theme

LIGHT = theme("daylight")
DARK = theme("midnight")
BODY_FONTS = UI_FONTS

_fonts_loaded = False


def load_fonts(assets_dir):
    """Register the bundled fonts once (Figtree, Bricolage Grotesque, JetBrains Mono)."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    _fonts_loaded = True
    folder = assets_dir / "fonts"
    for name in ("Figtree.ttf", "BricolageGrotesque.ttf", "JetBrainsMono.ttf"):
        path = folder / name
        if path.exists():
            QFontDatabase.addApplicationFont(os.fspath(path.resolve()))


def font_stack(families):
    return ", ".join(f'"{f}"' for f in families)


def build_qss(palette, scale=1.0):
    p = complete(palette)
    ui = font_stack(UI_FONTS)
    head = font_stack(HEADING_FONTS)
    code = font_stack(CODE_FONTS)

    def px(n):
        return f"{round(n * scale)}px"

    return f"""
    QMainWindow, QWidget {{
        background: {p['bg']};
        color: {p['text']};
        font-family: {ui};
        font-size: {px(13)};
    }}
    QDialog {{ background: {p['bg']}; }}
    QLabel {{ background: transparent; }}

    /* ---------- top bar ---------- */
    #TopBar {{ background: {p['chrome']}; border-bottom: 1px solid {p['line']}; }}
    #Wordmark {{ font-family: {head}; font-size: {px(19)}; font-weight: 800; }}
    #FileLabel, #Muted {{ color: {p['muted']}; font-size: {px(12)}; }}
    #FileName {{ color: {p['text']}; font-size: {px(13)}; font-weight: 600; }}
    #UpdateBar {{ background: {p['accent_soft']}; border-bottom: 1px solid {p['line']}; }}
    #UpdateBar QLabel {{ color: {p['text']}; font-size: {px(13)}; }}

    /* ---------- buttons ---------- */
    QPushButton {{
        background: {p['surface']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: {px(10)};
        padding: {px(6)} {px(13)};
        font-size: {px(13)};
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {p['surface2']}; }}
    QPushButton:pressed {{ background: {p['panel2']}; }}
    QPushButton:disabled {{ color: {p['faint']}; border-color: {p['line']}; }}
    QPushButton:focus {{ border-color: {p['focus']}; }}
    QPushButton#RunButton, QPushButton#Primary {{
        background: {p['accent']};
        color: {p['accent_text']};
        border: 1px solid {p['accent']};
        border-radius: {px(17)};
        padding: {px(7)} {px(18)};
        font-size: {px(14)};
        font-weight: 700;
    }}
    QPushButton#RunButton:hover, QPushButton#Primary:hover {{
        background: {p['accent_hover']}; border-color: {p['accent_hover']};
    }}
    QPushButton#RunButton:disabled {{
        background: {p['panel2']}; color: {p['faint']}; border-color: {p['panel2']};
    }}
    QPushButton#StopButton, QPushButton#StepButton {{
        background: transparent;
        border: 1px solid {p['border']};
        border-radius: {px(17)};
        padding: {px(7)} {px(14)};
    }}
    QPushButton#StopButton:enabled {{ color: {p['danger']}; border-color: {p['danger']}; }}
    QPushButton#StopButton:hover:enabled {{ background: {p['danger_soft']}; }}
    QPushButton#StepButton:hover {{ background: {p['surface2']}; }}
    QPushButton#GhostButton {{
        background: transparent;
        border: none;
        color: {p['muted']};
        padding: {px(6)} {px(10)};
    }}
    QPushButton#GhostButton:hover {{ color: {p['text']}; background: {p['surface2']}; }}
    QPushButton#LinkButton {{
        background: transparent; border: none; color: {p['accent']};
        padding: {px(2)} {px(4)}; font-weight: 700;
    }}
    QPushButton#LinkButton:hover {{ color: {p['accent_hover']}; }}
    QToolButton {{
        background: transparent;
        border: none;
        border-radius: {px(8)};
        padding: {px(5)};
        color: {p['muted']};
    }}
    QToolButton:hover {{ background: {p['surface2']}; color: {p['text']}; }}
    QToolButton:checked {{ background: {p['accent_soft']}; color: {p['accent']}; }}
    QToolButton:disabled {{ color: {p['faint']}; }}
    QToolButton::menu-indicator {{ image: none; width: 0; }}

    /* ---------- activity bar ---------- */
    #ActivityBar {{ background: {p['chrome']}; border-right: 1px solid {p['line']}; }}
    QToolButton#ActivityButton {{ border-radius: {px(11)}; padding: {px(9)}; }}
    QToolButton#ActivityButton:checked {{ background: {p['accent_soft']}; }}

    /* ---------- cards and panels ---------- */
    #Card {{
        background: {p['surface']};
        border: 1px solid {p['line']};
        border-radius: {px(14)};
    }}
    #CardHeader {{ background: transparent; }}
    #CardTitle {{
        color: {p['muted']}; font-size: {px(11)}; font-weight: 800;
        font-family: {ui}; padding: 0;
    }}
    #SidePanel {{ background: {p['panel']}; }}
    QLabel#SectionTitle {{
        color: {p['muted']}; font-size: {px(11)}; font-weight: 800; padding: {px(10)} {px(2)} {px(4)} {px(2)};
    }}
    QLabel#PanelTitle, QLabel#StageTitle {{
        color: {p['muted']}; font-size: {px(11)}; font-weight: 800; padding: {px(6)} {px(10)};
    }}
    #Heading {{ font-family: {head}; font-size: {px(22)}; font-weight: 800; }}
    #HeroTitle {{ font-family: {head}; font-size: {px(34)}; font-weight: 800; }}
    #SubHeading {{ font-family: {head}; font-size: {px(16)}; font-weight: 700; }}
    #Badge {{
        background: {p['accent']}; color: {p['accent_text']}; border-radius: {px(7)};
        font-size: {px(10)}; font-weight: 800; padding: 0 {px(4)};
    }}
    #Pill {{
        background: {p['surface2']}; color: {p['muted']}; border-radius: {px(9)};
        padding: {px(2)} {px(9)}; font-size: {px(12)}; font-weight: 600;
    }}
    #Pill[state="running"] {{ background: {p['info_soft']}; color: {p['sky']}; }}
    #Pill[state="done"] {{ background: {p['success_soft']}; color: {p['success']}; }}
    #Pill[state="error"] {{ background: {p['danger_soft']}; color: {p['danger']}; }}
    #Pill[state="paused"] {{ background: {p['accent_soft']}; color: {p['accent']}; }}
    #Toast {{
        background: {p['text']}; color: {p['bg']}; border-radius: {px(12)};
        padding: {px(9)} {px(16)}; font-size: {px(13)}; font-weight: 600;
    }}

    /* ---------- home ---------- */
    #HomePage, #HomeInner {{ background: {p['bg']}; }}
    #HomeCard {{
        background: {p['surface']};
        border: 1px solid {p['line']};
        border-radius: {px(16)};
    }}
    #HomeCard:hover {{ border-color: {p['accent']}; }}
    #HomeCard QLabel {{ background: transparent; }}
    #CardText {{ color: {p['muted']}; font-size: {px(12)}; }}

    /* ---------- editor, console, inputs ---------- */
    QPlainTextEdit#Editor {{
        background: {p['editor_bg']};
        color: {p['text']};
        border: none;
        font-family: {code};
        font-size: {px(15)};
        selection-background-color: {p['sel']};
        selection-color: {p['text']};
    }}
    QPlainTextEdit#Console, QTextBrowser#Console {{
        background: {p['surface']};
        color: {p['text']};
        border: none;
        font-family: {code};
        font-size: {px(13)};
        padding: {px(4)};
        selection-background-color: {p['sel']};
    }}
    QLineEdit#AskInput {{
        background: {p['editor_bg']};
        border: 1.5px solid {p['sky']};
        border-radius: {px(10)};
        padding: {px(6)} {px(10)};
        font-family: {code};
    }}
    QLineEdit#AskInput:disabled {{ border-color: {p['line']}; background: {p['surface']}; color: {p['faint']}; }}
    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit#Field {{
        background: {p['surface']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: {px(9)};
        padding: {px(5)} {px(9)};
        selection-background-color: {p['sel']};
        selection-color: {p['text']};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit#Field:focus {{ border-color: {p['focus']}; }}
    QComboBox::drop-down {{ border: none; width: {px(22)}; }}
    QComboBox QAbstractItemView {{
        background: {p['surface']}; border: 1px solid {p['border']}; border-radius: {px(8)};
        selection-background-color: {p['accent_soft']}; selection-color: {p['text']};
    }}
    QCheckBox, QRadioButton {{ spacing: {px(8)}; background: transparent; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: {px(16)}; height: {px(16)}; border: 1.5px solid {p['faint']};
        border-radius: {px(5)}; background: {p['surface']};
    }}
    QRadioButton::indicator {{ border-radius: {px(9)}; }}
    QRadioButton::indicator:checked {{ border: {px(5)} solid {p['accent']}; background: {p['surface']}; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {p['accent']}; border-color: {p['accent']};
    }}
    QPlainTextEdit#AskBox {{
        background: {p['surface']}; border: 1px solid {p['border']}; border-radius: {px(10)};
        padding: {px(6)}; font-size: {px(13)};
    }}
    QTextBrowser {{
        background: {p['surface']}; border: 1px solid {p['line']}; border-radius: {px(10)};
        padding: {px(8)}; font-size: {px(13)};
    }}

    /* ---------- tabs ---------- */
    QTabWidget#EditorTabs::pane {{ border: none; }}
    QTabBar {{ background: {p['panel']}; }}
    QTabBar::tab {{
        background: transparent;
        color: {p['muted']};
        padding: {px(8)} {px(14)};
        margin: {px(5)} 0 0 {px(4)};
        border: 1px solid transparent;
        border-top-left-radius: {px(9)};
        border-top-right-radius: {px(9)};
        font-size: {px(12)};
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {p['editor_bg']};
        color: {p['text']};
        border-color: {p['line']};
        border-bottom-color: {p['editor_bg']};
    }}
    QTabBar::tab:hover:!selected {{ color: {p['text']}; background: {p['surface2']}; }}
    QTabWidget::pane {{ border: 1px solid {p['line']}; border-radius: {px(10)}; }}

    /* ---------- lists, trees, menus ---------- */
    QListWidget, QTreeView, QListView {{
        background: {p['surface']};
        color: {p['text']};
        border: 1px solid {p['line']};
        border-radius: {px(10)};
        padding: {px(4)};
        font-size: {px(13)};
        outline: none;
    }}
    QListWidget::item, QTreeView::item {{ padding: {px(6)} {px(7)}; border-radius: {px(7)}; }}
    QListWidget::item:selected, QTreeView::item:selected {{ background: {p['accent_soft']}; color: {p['text']}; }}
    QListWidget::item:hover, QTreeView::item:hover {{ background: {p['surface2']}; }}
    QListWidget#SettingsNav {{ background: transparent; border: none; padding: 0; }}
    QListWidget#SettingsNav::item {{ padding: {px(8)} {px(12)}; margin: {px(1)} 0; font-weight: 600; }}
    QListWidget#SettingsNav::item:selected {{ background: {p['accent_soft']}; color: {p['accent']}; }}
    QMenuBar {{ background: {p['chrome']}; }}
    QMenuBar::item:selected {{ background: {p['surface2']}; border-radius: {px(6)}; }}
    QMenu {{
        background: {p['surface']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: {px(12)};
        padding: {px(6)};
    }}
    QMenu::item {{ padding: {px(7)} {px(26)} {px(7)} {px(12)}; border-radius: {px(8)}; }}
    QMenu::item:selected {{ background: {p['accent_soft']}; }}
    QMenu::item:disabled {{ color: {p['faint']}; }}
    QMenu::separator {{ height: 1px; background: {p['line']}; margin: {px(5)} {px(8)}; }}
    QMenu::icon {{ padding-left: {px(8)}; }}
    QDialog#Palette {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: {px(14)}; }}
    QDialog#Palette QLineEdit {{ font-size: {px(15)}; padding: {px(9)} {px(12)}; }}
    QDialog#Palette QListWidget {{ border: none; }}

    /* ---------- chrome ---------- */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QWidget#BlockPanel {{ background: {p['panel']}; }}
    QSplitter::handle {{ background: {p['line']}; }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}
    QSplitter#Workspace::handle {{ background: transparent; width: {px(8)}; height: {px(8)}; }}
    QStatusBar {{
        background: {p['chrome']};
        color: {p['muted']};
        border-top: 1px solid {p['line']};
        font-size: {px(12)};
    }}
    QStatusBar::item {{ border: none; }}
    QSlider::groove:horizontal {{ height: {px(4)}; background: {p['panel2']}; border-radius: {px(2)}; }}
    QSlider::sub-page:horizontal {{ background: {p['accent']}; border-radius: {px(2)}; }}
    QSlider::handle:horizontal {{
        width: {px(16)}; height: {px(16)}; margin: -{px(6)} 0;
        border-radius: {px(8)}; background: {p['surface']}; border: 2px solid {p['accent']};
    }}
    QScrollBar:vertical {{ background: transparent; width: {px(10)}; margin: {px(2)}; }}
    QScrollBar::handle:vertical {{ background: {p['faint']}; border-radius: {px(4)}; min-height: {px(24)}; }}
    QScrollBar:horizontal {{ background: transparent; height: {px(10)}; margin: {px(2)}; }}
    QScrollBar::handle:horizontal {{ background: {p['faint']}; border-radius: {px(4)}; min-width: {px(24)}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        height: 0; width: 0; background: transparent;
    }}
    QToolTip {{
        background: {p['text']}; color: {p['bg']}; border: none;
        padding: {px(6)} {px(9)}; font-size: {px(12)};
    }}
    #FindBar {{ background: {p['panel']}; border-bottom: 1px solid {p['line']}; }}
    QProgressBar {{
        background: {p['panel2']}; border: none; border-radius: {px(4)}; height: {px(8)};
        text-align: center; color: transparent;
    }}
    QProgressBar::chunk {{ background: {p['accent']}; border-radius: {px(4)}; }}

    /* ---------- stage tools (Sparky 3) ---------- */
    #RecLabel {{ color: {p['danger']}; font-size: {px(12)}; font-weight: 700; padding-right: {px(6)}; }}
    #SpritesTable {{
        background: {p['surface']}; border: 1px solid {p['line']}; border-radius: {px(10)};
        gridline-color: transparent; font-size: {px(12)};
    }}
    #SpritesTable QHeaderView::section {{
        background: {p['panel']}; color: {p['muted']}; border: none;
        border-bottom: 1px solid {p['line']}; padding: {px(3)} {px(6)}; font-size: {px(11)};
    }}
    #CostumeButton {{
        background: {p['surface']}; border: 1px solid {p['line']}; border-radius: {px(12)};
        font-size: {px(11)}; color: {p['muted']};
    }}
    #CostumeButton:hover {{ border-color: {p['accent']}; background: {p['accent_soft']}; color: {p['text']}; }}
    """
