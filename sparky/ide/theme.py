# Sparky IDE theming: warm cream & ink palette with coral/sky/sage accents,
# in light and dark. One QSS stylesheet built from a palette dict.

LIGHT = {
    "bg":        "#faf9f5",   # cream
    "panel":     "#f1efe7",
    "panel2":    "#e8e6dc",   # light gray
    "border":    "#dcd9cc",
    "text":      "#141413",   # ink
    "muted":     "#8a887e",
    "faint":     "#b0aea5",   # mid gray
    "accent":    "#d97757",   # coral orange
    "accent2":   "#6a9bcc",   # sky blue
    "accent3":   "#788c5d",   # sage green
    "editor_bg": "#fffdf8",
    "line_hl":   "#f3f0e5",
    "run_hl":    "#e3ecf5",
    "err_hl":    "#f7e3dc",
    "gutter":    "#b0aea5",
    "sel":       "#ead9c5",
    # syntax colors
    "syn_cmd":   "#c05d3d",
    "syn_word":  "#5a86b5",
    "syn_str":   "#6f8253",
    "syn_num":   "#8e6bb5",
    "syn_com":   "#a5a396",
}

DARK = {
    "bg":        "#141413",
    "panel":     "#1d1c1a",
    "panel2":    "#262522",
    "border":    "#33322e",
    "text":      "#faf9f5",
    "muted":     "#9a988e",
    "faint":     "#6e6c64",
    "accent":    "#d97757",
    "accent2":   "#6a9bcc",
    "accent3":   "#8fa377",
    "editor_bg": "#191817",
    "line_hl":   "#211f1d",
    "run_hl":    "#22303d",
    "err_hl":    "#3d2620",
    "gutter":    "#6e6c64",
    "sel":       "#4a3a2c",
    "syn_cmd":   "#e08b6d",
    "syn_word":  "#85aed6",
    "syn_str":   "#a3b884",
    "syn_num":   "#b596d9",
    "syn_com":   "#767468",
}

HEADING_FONTS = ["Poppins", "Avenir Next", "Helvetica Neue", "Segoe UI", "Ubuntu",
                 "Cantarell", "Noto Sans", "DejaVu Sans", "Arial"]
BODY_FONTS = ["Lora", "Georgia", "Noto Serif", "DejaVu Serif", "Times New Roman"]
CODE_FONTS = ["SF Mono", "Menlo", "Monaco", "Cascadia Mono", "Consolas", "Ubuntu Mono",
              "DejaVu Sans Mono", "Liberation Mono", "Courier New"]


def font_stack(families):
    return ", ".join(f'"{f}"' for f in families)


def build_qss(p):
    heading = font_stack(HEADING_FONTS)
    body = font_stack(BODY_FONTS)
    code = font_stack(CODE_FONTS)
    return f"""
    QMainWindow, QWidget {{
        background: {p['bg']};
        color: {p['text']};
        font-family: {body};
        font-size: 14px;
    }}
    #HeaderBar {{
        background: {p['bg']};
        border-bottom: 1px solid {p['border']};
    }}
    #AppTitle {{
        font-family: {heading};
        font-size: 19px;
        font-weight: 700;
        color: {p['text']};
    }}
    #FileLabel {{
        color: {p['muted']};
        font-size: 13px;
    }}
    QPushButton {{
        background: {p['panel2']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 9px;
        padding: 7px 14px;
        font-family: {heading};
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {p['panel']}; border-color: {p['faint']}; }}
    QPushButton:pressed {{ background: {p['border']}; }}
    QPushButton:disabled {{ color: {p['faint']}; }}
    QPushButton#RunButton {{
        background: {p['accent']};
        color: #ffffff;
        border: none;
        padding: 7px 20px;
    }}
    QPushButton#RunButton:hover {{ background: #c9654a; }}
    QPushButton#RunButton:disabled {{ background: {p['faint']}; }}
    QPushButton#StopButton {{
        background: transparent;
        color: {p['accent']};
        border: 1.5px solid {p['accent']};
        padding: 6px 16px;
    }}
    QPushButton#StopButton:hover {{ background: {p['err_hl']}; }}
    QPushButton#StopButton:disabled {{
        color: {p['faint']}; border-color: {p['faint']}; background: transparent;
    }}
    QPushButton#GhostButton {{
        background: transparent;
        border: none;
        color: {p['muted']};
        padding: 7px 10px;
    }}
    QPushButton#GhostButton:hover {{ color: {p['text']}; background: {p['panel2']}; }}
    QPlainTextEdit#Editor {{
        background: {p['editor_bg']};
        color: {p['text']};
        border: none;
        font-family: {code};
        font-size: 15px;
        selection-background-color: {p['sel']};
        selection-color: {p['text']};
    }}
    QPlainTextEdit#Console {{
        background: {p['panel']};
        color: {p['text']};
        border: none;
        border-top: 1px solid {p['border']};
        font-family: {code};
        font-size: 13px;
        padding: 6px;
        selection-background-color: {p['sel']};
    }}
    QLineEdit#AskInput {{
        background: {p['editor_bg']};
        color: {p['text']};
        border: 1.5px solid {p['accent2']};
        border-radius: 9px;
        padding: 6px 10px;
        font-family: {code};
        font-size: 13px;
    }}
    QLineEdit#AskInput:disabled {{
        border-color: {p['border']};
        background: {p['panel']};
        color: {p['faint']};
    }}
    QLabel#SectionTitle {{
        font-family: {heading};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        color: {p['muted']};
        padding: 10px 4px 2px 4px;
    }}
    QLabel#StageTitle, QLabel#PanelTitle {{
        font-family: {heading};
        font-size: 12px;
        font-weight: 700;
        color: {p['muted']};
        padding: 6px 10px;
    }}
    QScrollArea {{ border: none; background: {p['panel']}; }}
    QWidget#BlockPanel {{ background: {p['panel']}; }}
    QSplitter::handle {{ background: {p['border']}; }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}
    QStatusBar {{
        background: {p['bg']};
        color: {p['muted']};
        border-top: 1px solid {p['border']};
        font-size: 12px;
    }}
    QSlider::groove:horizontal {{
        height: 4px; background: {p['panel2']}; border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px; height: 14px; margin: -5px 0;
        border-radius: 7px; background: {p['accent']};
    }}
    QMenu {{
        background: {p['bg']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{ padding: 6px 22px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {p['panel2']}; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['faint']}; border-radius: 4px; min-height: 24px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar:horizontal {{
        background: transparent; height: 10px; margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p['faint']}; border-radius: 4px; min-width: 24px;
    }}
    QToolTip {{
        background: {p['text']};
        color: {p['bg']};
        border: none;
        padding: 5px 8px;
        font-size: 12px;
    }}
    QListView {{
        background: {p['bg']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        font-family: {code};
        font-size: 13px;
    }}
    QListWidget, QTreeView {{
        background: {p['panel']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        font-family: {body};
        font-size: 13px;
        padding: 4px;
    }}
    QListWidget::item, QTreeView::item {{ padding: 5px 6px; border-radius: 6px; }}
    QListWidget::item:selected, QTreeView::item:selected {{
        background: {p['sel']}; color: {p['text']};
    }}
    QListWidget::item:hover, QTreeView::item:hover {{ background: {p['panel2']}; }}
    #ActivityBar {{
        background: {p['panel2']};
        border-right: 1px solid {p['border']};
    }}
    QToolButton#ActivityButton {{
        background: transparent;
        border: none;
        border-radius: 10px;
        font-size: 19px;
        padding: 8px;
        min-width: 30px;
    }}
    QToolButton#ActivityButton:hover {{ background: {p['panel']}; }}
    QToolButton#ActivityButton:checked {{
        background: {p['bg']};
        border-left: 3px solid {p['accent']};
    }}
    QTabWidget#EditorTabs::pane {{ border: none; }}
    QTabBar {{ background: {p['panel']}; }}
    QTabBar::tab {{
        background: {p['panel']};
        color: {p['muted']};
        padding: 8px 14px;
        border: none;
        border-right: 1px solid {p['border']};
        font-family: {heading};
        font-size: 12px;
    }}
    QTabBar::tab:selected {{
        background: {p['editor_bg']};
        color: {p['text']};
        border-top: 2px solid {p['accent']};
    }}
    QTabBar::tab:hover {{ color: {p['text']}; }}
    #FindBar {{
        background: {p['panel']};
        border-bottom: 1px solid {p['border']};
    }}
    QLineEdit, QComboBox, QSpinBox {{
        background: {p['editor_bg']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 7px;
        padding: 5px 8px;
        selection-background-color: {p['sel']};
    }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {p['accent2']}; }}
    QPlainTextEdit#AskBox {{
        background: {p['editor_bg']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 9px;
        padding: 6px;
        font-family: {body};
        font-size: 13px;
    }}
    QTextBrowser {{
        background: {p['editor_bg']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 9px;
        padding: 6px;
        font-family: {body};
        font-size: 13px;
    }}
    QDialog#Palette {{
        background: {p['bg']};
        border: 1px solid {p['border']};
        border-radius: 12px;
    }}
    QTabWidget::pane {{ border: 1px solid {p['border']}; border-radius: 8px; }}
    """
