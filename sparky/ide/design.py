# Spark 3: Sparky's design tokens.
#
# Every color in the app comes from a named token, so a theme is just a
# dict of tokens. The same values are used on sparky-code.web.app.
# The older keys (bg, panel, panel2, border, accent2…) are kept because
# VS Code themes and older code use them; complete() fills in the new keys
# for any palette that only has the old ones.

from PyQt6.QtGui import QColor

RADIUS_S, RADIUS_M, RADIUS_L = 8, 12, 18
SPACE = 4          # the spacing grid

UI_FONTS = ["Figtree", "Avenir Next", "Segoe UI", "Ubuntu", "Cantarell", "Noto Sans",
            "Helvetica Neue", "Arial"]
HEADING_FONTS = ["Bricolage Grotesque", "Figtree", "Avenir Next", "Segoe UI", "Ubuntu",
                 "Helvetica Neue", "Arial"]
CODE_FONTS = ["JetBrains Mono", "SF Mono", "Menlo", "Cascadia Mono", "Consolas",
              "Ubuntu Mono", "DejaVu Sans Mono", "Courier New"]

DAYLIGHT = {
    "name": "Daylight", "dark": False,
    "bg": "#faf9f5", "chrome": "#f3f1ea", "panel": "#f3f1ea", "panel2": "#e9e6dc",
    "surface": "#fffefb", "surface2": "#f1efe7", "border": "#e2ded2", "line": "#e7e3d8",
    "text": "#141413", "muted": "#6f6d66", "faint": "#aeaba1",
    "accent": "#d97757", "accent_hover": "#c6623f", "accent_text": "#ffffff",
    "accent_soft": "#f8e6dd", "accent2": "#3f7fbf", "accent3": "#6f8a4f",
    "sky": "#3f7fbf", "sage": "#6f8a4f", "sun": "#c08a1c", "grape": "#7f62c4",
    "danger": "#c4432b", "danger_soft": "#f8e1d9", "success": "#3f8a52",
    "success_soft": "#e3f0e2", "info_soft": "#e2edf7", "focus": "#3f7fbf",
    "editor_bg": "#fffefb", "line_hl": "#f6f3ea", "run_hl": "#e2edf7", "err_hl": "#f8e1d9",
    "gutter": "#b4b1a6", "sel": "#f0dccd",
    "stage_bg": "#ffffff", "stage_grid": "#ece8dd",
    "syn_cmd": "#c0532f", "syn_word": "#3f75ad", "syn_str": "#5f7d3a",
    "syn_num": "#8a5cc2", "syn_com": "#a3a094",
}

MIDNIGHT = {
    "name": "Midnight", "dark": True,
    "bg": "#141413", "chrome": "#191917", "panel": "#1c1b19", "panel2": "#26241f",
    "surface": "#1d1c1a", "surface2": "#28261f", "border": "#33312b", "line": "#2b2925",
    "text": "#f3f1ea", "muted": "#a3a097", "faint": "#6c6a62",
    "accent": "#e08260", "accent_hover": "#eb9a7c", "accent_text": "#141413",
    "accent_soft": "#3a2620", "accent2": "#7fb0dd", "accent3": "#9bb07f",
    "sky": "#7fb0dd", "sage": "#9bb07f", "sun": "#e8b44a", "grape": "#b39ae6",
    "danger": "#ef7a60", "danger_soft": "#40241d", "success": "#7cc08a",
    "success_soft": "#1f3324", "info_soft": "#1f3243", "focus": "#7fb0dd",
    "editor_bg": "#171615", "line_hl": "#1f1d1b", "run_hl": "#1f3243", "err_hl": "#40241d",
    "gutter": "#5f5d56", "sel": "#4a3528",
    "stage_bg": "#1b1a18", "stage_grid": "#2a2824",
    "syn_cmd": "#ec9474", "syn_word": "#8cb8e3", "syn_str": "#a9c38a",
    "syn_num": "#c2a4ea", "syn_com": "#75736a",
}

CANDY = {
    "name": "Candy", "dark": False,
    "bg": "#fff7ef", "chrome": "#ffeedf", "panel": "#ffefe1", "panel2": "#ffe0c8",
    "surface": "#ffffff", "surface2": "#fff1e4", "border": "#f3d3ba", "line": "#f6dfcc",
    "text": "#2b1d3a", "muted": "#76658a", "faint": "#b9a9c6",
    "accent": "#ff6b4a", "accent_hover": "#f2532f", "accent_text": "#ffffff",
    "accent_soft": "#ffe1d8", "accent2": "#2f8fe0", "accent3": "#2fa36b",
    "sky": "#2f8fe0", "sage": "#2fa36b", "sun": "#f5a623", "grape": "#8a5cf6",
    "danger": "#e5383b", "danger_soft": "#ffe0dc", "success": "#2fa36b",
    "success_soft": "#ddf5e8", "info_soft": "#e3f0ff", "focus": "#8a5cf6",
    "editor_bg": "#fffdfa", "line_hl": "#fff3e6", "run_hl": "#e3f0ff", "err_hl": "#ffe0dc",
    "gutter": "#c6b3a3", "sel": "#ffd6c2",
    "stage_bg": "#ffffff", "stage_grid": "#ffe9d6",
    "syn_cmd": "#e5482b", "syn_word": "#2f7fd0", "syn_str": "#2b9a5f",
    "syn_num": "#8a5cf6", "syn_com": "#b29f90",
}

CONTRAST = {
    "name": "High Contrast", "dark": True,
    "bg": "#000000", "chrome": "#000000", "panel": "#0b0b0b", "panel2": "#1c1c1c",
    "surface": "#000000", "surface2": "#1c1c1c", "border": "#ffffff", "line": "#9a9a9a",
    "text": "#ffffff", "muted": "#e8e8e8", "faint": "#c2c2c2",
    "accent": "#ffa06b", "accent_hover": "#ffc09e", "accent_text": "#000000",
    "accent_soft": "#3d2010", "accent2": "#66ccff", "accent3": "#8cff8c",
    "sky": "#66ccff", "sage": "#8cff8c", "sun": "#ffe066", "grape": "#dcb0ff",
    "danger": "#ff7b7b", "danger_soft": "#4d0000", "success": "#8cff8c",
    "success_soft": "#003300", "info_soft": "#002a4d", "focus": "#ffe066",
    "editor_bg": "#000000", "line_hl": "#1c1c1c", "run_hl": "#003366", "err_hl": "#4d0000",
    "gutter": "#c2c2c2", "sel": "#0055aa",
    "stage_bg": "#000000", "stage_grid": "#333333",
    "syn_cmd": "#ffb07a", "syn_word": "#7fd4ff", "syn_str": "#a6ff8f",
    "syn_num": "#e2b3ff", "syn_com": "#c2c2c2",
}

THEMES = {"daylight": DAYLIGHT, "midnight": MIDNIGHT, "candy": CANDY, "contrast": CONTRAST}
OLD_NAMES = {"light": "daylight", "dark": "midnight"}


def _mix(a, b, t):
    ca, cb = QColor(a), QColor(b)
    return QColor(round(ca.red() + (cb.red() - ca.red()) * t),
                  round(ca.green() + (cb.green() - ca.green()) * t),
                  round(ca.blue() + (cb.blue() - ca.blue()) * t)).name()


def is_dark(palette):
    return QColor(palette.get("editor_bg", palette.get("bg", "#ffffff"))).lightness() < 128


def complete(palette):
    """Fill in Spark 3 tokens for a palette that only has the older keys."""
    p = dict(palette)
    dark = is_dark(p)
    base = MIDNIGHT if dark else DAYLIGHT
    p.setdefault("dark", dark)
    p.setdefault("name", "Custom")
    p.setdefault("chrome", p.get("panel", base["chrome"]))
    p.setdefault("surface", p.get("editor_bg", base["surface"]))
    p.setdefault("surface2", p.get("panel2", base["surface2"]))
    p.setdefault("line", p.get("border", base["line"]))
    accent = p.get("accent", base["accent"])
    p.setdefault("accent_hover", _mix(accent, "#ffffff" if dark else "#000000", 0.12))
    p.setdefault("accent_text", "#141413" if QColor(accent).lightness() > 150 else "#ffffff")
    p.setdefault("accent_soft", _mix(p.get("bg", base["bg"]), accent, 0.18))
    for key in ("sky", "sage", "sun", "grape", "danger", "success", "focus",
                "danger_soft", "success_soft", "info_soft", "stage_grid"):
        p.setdefault(key, base[key])
    p.setdefault("stage_bg", p.get("editor_bg", base["stage_bg"]))
    for key, value in base.items():
        p.setdefault(key, value)
    return p


def theme(key):
    """The palette for a built-in theme key (old 'light'/'dark' names still work)."""
    key = OLD_NAMES.get(key, key)
    return complete(THEMES.get(key, DAYLIGHT))
