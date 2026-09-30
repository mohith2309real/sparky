# VS Code extension support: color themes and snippets.
#
# A .vsix file is a zip with extension/package.json describing what it
# "contributes". Sparky reads only the parts it can use safely — color
# themes and code snippets — and never runs any code from an extension.
# Extensions can come from a .vsix file or from Open VSX (open-vsx.org),
# the open marketplace that VS Code-compatible editors share.

import json
import plistlib
import posixpath
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from ..paths import USER_DIR

VSCODE_DIR = USER_DIR / "vscode-extensions"
OPEN_VSX = "https://open-vsx.org/api/-/search"
MAX_FILE = 5 * 1024 * 1024
USER_AGENT = "Sparky-IDE/1.1 (+https://sparky-code.web.app)"


def ssl_context():
    """HTTPS certificates that also work inside bundled apps."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


# ---------- tolerant JSON (VS Code files allow comments and trailing commas) ----------

def parse_jsonc(text):
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(ch)
            i += 1
    cleaned = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    return json.loads(cleaned)


# ---------- installing ----------

class ExtensionError(Exception):
    pass


def _safe_join(root, relative):
    relative = posixpath.normpath(relative.replace("\\", "/")).lstrip("/")
    if relative.startswith(".."):
        raise ExtensionError(f"unsafe path in extension: {relative}")
    return root / relative


def install_vsix(vsix_path):
    """Install themes and snippets from a .vsix. Returns the extension summary."""
    try:
        archive = zipfile.ZipFile(vsix_path)
    except (zipfile.BadZipFile, OSError) as err:
        raise ExtensionError(f"That isn't a VS Code extension file ({err}).")
    with archive:
        try:
            manifest = parse_jsonc(archive.read("extension/package.json").decode("utf-8-sig"))
        except KeyError:
            raise ExtensionError("That .vsix has no extension/package.json.")
        publisher = manifest.get("publisher", "unknown")
        name = manifest.get("name", Path(vsix_path).stem)
        ext_id = f"{publisher}.{name}".lower()
        contributes = manifest.get("contributes", {})
        themes = [t for t in contributes.get("themes", []) if t.get("path")]
        snippets = [s for s in contributes.get("snippets", []) if s.get("path")]
        if not themes and not snippets:
            raise ExtensionError(f'"{manifest.get("displayName", name)}" has no color '
                                 "themes or snippets — Sparky can use only those.")

        target = VSCODE_DIR / ext_id
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        wanted = {posixpath.normpath("extension/" + x["path"].lstrip("./"))
                  for x in themes + snippets}
        names = set(archive.namelist())

        def copy(member):
            info = archive.getinfo(member)
            if info.file_size > MAX_FILE:
                raise ExtensionError(f"{member} is too big to be a theme or snippet file.")
            dest = _safe_join(target, member[len("extension/"):])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(member))

        for member in wanted:
            if member in names:
                copy(member)
                # themes may "include" a base theme file next to them
                try:
                    data = parse_jsonc(archive.read(member).decode("utf-8-sig"))
                except (ValueError, UnicodeDecodeError):
                    data = {}
                include = data.get("include") if isinstance(data, dict) else None
                if include:
                    inc = posixpath.normpath(posixpath.join(posixpath.dirname(member), include))
                    if inc in names:
                        copy(inc)
                token_file = data.get("tokenColors") if isinstance(data, dict) else None
                if isinstance(token_file, str):
                    inc = posixpath.normpath(posixpath.join(posixpath.dirname(member),
                                                            token_file))
                    if inc in names:
                        copy(inc)

    summary = {
        "id": ext_id,
        "name": manifest.get("displayName") or name,
        "publisher": publisher,
        "version": manifest.get("version", ""),
        "description": manifest.get("description", ""),
        "themes": [{"label": t.get("label") or t.get("id") or Path(t["path"]).stem,
                    "ui": t.get("uiTheme", "vs-dark"),
                    "path": t["path"].lstrip("./")} for t in themes],
        "snippets": [{"language": s.get("language", ""),
                      "path": s["path"].lstrip("./")} for s in snippets],
    }
    (target / "sparky-extension.json").write_text(json.dumps(summary, indent=2))
    return summary


def installed():
    if not VSCODE_DIR.is_dir():
        return []
    found = []
    for meta in sorted(VSCODE_DIR.glob("*/sparky-extension.json")):
        try:
            found.append(json.loads(meta.read_text()))
        except (OSError, ValueError):
            continue
    return found


def uninstall(ext_id):
    target = VSCODE_DIR / ext_id
    if target.is_dir() and target.parent == VSCODE_DIR:
        shutil.rmtree(target)


# ---------- themes ----------

def _load_theme_file(path, depth=0):
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".tmtheme":
        plist = plistlib.loads(text.encode("utf-8"))
        return {"tokenColors": plist.get("settings", [])}
    data = parse_jsonc(text)
    if depth < 3 and data.get("include"):
        base = _load_theme_file(path.parent / data["include"], depth + 1)
        merged = dict(base)
        merged["colors"] = {**base.get("colors", {}), **data.get("colors", {})}
        merged["tokenColors"] = list(base.get("tokenColors", [])) + \
            list(data.get("tokenColors", []) if isinstance(data.get("tokenColors"), list) else [])
        for key in ("type", "name"):
            if key in data:
                merged[key] = data[key]
        data = merged
    if isinstance(data.get("tokenColors"), str):
        extra = _load_theme_file(path.parent / data["tokenColors"], depth + 1)
        data["tokenColors"] = extra.get("tokenColors", [])
    return data


def all_themes():
    """[(theme key, label, is_dark)] for every installed VS Code theme."""
    themes = []
    for ext in installed():
        for t in ext["themes"]:
            key = f"vscode:{ext['id']}:{t['label']}"
            themes.append((key, t["label"], t["ui"] not in ("vs", "hc-light")))
    return themes


def _hex(color, under=None):
    """VS Code colors are #rgb, #rrggbb or #rrggbbaa; Qt wants opaque #rrggbb."""
    if not isinstance(color, str) or not color.startswith("#"):
        return None
    c = color[1:]
    if len(c) in (3, 4):
        c = "".join(ch * 2 for ch in c)
    if len(c) == 6:
        return "#" + c.lower()
    if len(c) == 8:
        rgb, alpha = c[:6], int(c[6:], 16) / 255
        base = (under or "#000000").lstrip("#")
        mixed = [round(int(rgb[i:i + 2], 16) * alpha + int(base[i:i + 2], 16) * (1 - alpha))
                 for i in (0, 2, 4)]
        return "#" + "".join(f"{v:02x}" for v in mixed)
    return None


def _mix(a, b, amount):
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(f"{round(int(a[i:i + 2], 16) * (1 - amount) + int(b[i:i + 2], 16) * amount):02x}"
                         for i in (0, 2, 4))


def theme_palette(key, light, dark):
    """Turn an installed VS Code theme into a Sparky palette."""
    _, ext_id, label = key.split(":", 2)
    ext = next((e for e in installed() if e["id"] == ext_id), None)
    if ext is None:
        return None
    entry = next((t for t in ext["themes"] if t["label"] == label), None)
    if entry is None:
        return None
    theme = _load_theme_file(VSCODE_DIR / ext_id / entry["path"])
    is_dark = entry["ui"] not in ("vs", "hc-light")
    p = dict(dark if is_dark else light)
    colors = theme.get("colors", {})

    def pick(*keys, under=None):
        for k in keys:
            value = _hex(colors.get(k), under)
            if value:
                return value
        return None

    editor_bg = pick("editor.background") or p["editor_bg"]
    p["editor_bg"] = editor_bg
    p["text"] = pick("editor.foreground", "foreground", under=editor_bg) or p["text"]
    p["bg"] = pick("titleBar.activeBackground", "sideBar.background",
                   "editorGroupHeader.tabsBackground", under=editor_bg) or editor_bg
    p["panel"] = pick("sideBar.background", "panel.background", under=editor_bg) or p["panel"]
    p["panel2"] = pick("input.background", "dropdown.background", "tab.inactiveBackground",
                       under=editor_bg) or _mix(p["panel"], p["text"], 0.08)
    p["border"] = pick("panel.border", "sideBar.border", "editorGroup.border",
                       "contrastBorder", under=editor_bg) or _mix(editor_bg, p["text"], 0.15)
    p["muted"] = pick("descriptionForeground", "tab.inactiveForeground",
                      "sideBar.foreground", under=editor_bg) or _mix(p["text"], editor_bg, 0.4)
    p["faint"] = _mix(p["muted"], editor_bg, 0.35)
    p["accent"] = pick("button.background", "activityBarBadge.background", "focusBorder",
                       under=editor_bg) or p["accent"]
    p["accent2"] = pick("textLink.foreground", "progressBar.background",
                        under=editor_bg) or p["accent2"]
    p["line_hl"] = pick("editor.lineHighlightBackground", under=editor_bg) or \
        _mix(editor_bg, p["text"], 0.05)
    p["sel"] = pick("editor.selectionBackground", under=editor_bg) or _mix(editor_bg, p["accent2"], 0.3)
    p["gutter"] = pick("editorLineNumber.foreground", under=editor_bg) or p["muted"]
    p["run_hl"] = _mix(editor_bg, p["accent2"], 0.22)
    p["err_hl"] = _mix(editor_bg, p["accent"], 0.22)

    wanted = {
        "syn_com": ("comment",),
        "syn_str": ("string",),
        "syn_num": ("constant.numeric", "constant"),
        "syn_cmd": ("keyword.control", "keyword", "storage.type", "storage"),
        "syn_word": ("support.function", "entity.name.function", "variable.language",
                     "support", "variable"),
    }
    scopes = {}
    for rule in theme.get("tokenColors", []):
        if not isinstance(rule, dict):
            continue
        fg = _hex(rule.get("settings", {}).get("foreground"), editor_bg)
        scope = rule.get("scope")
        if not fg or not scope:
            continue
        for s in ([scope] if isinstance(scope, str) else scope):
            for part in str(s).split(","):
                scopes.setdefault(part.strip(), fg)
    for token, candidates in wanted.items():
        for scope in candidates:
            if scope in scopes:
                p[token] = scopes[scope]
                break
    p["theme_name"] = label
    return p


# ---------- snippets ----------

LANGUAGE_ALIASES = {"javascript": ("javascript", "javascriptreact"),
                    "python": ("python",), "html": ("html",), "css": ("css",),
                    "json": ("json", "jsonc"), "markdown": ("markdown",),
                    "sparky": ("sparky",)}


def snippets_for(language_id):
    """{prefix: (body, description)} from every installed extension."""
    names = LANGUAGE_ALIASES.get(language_id, (language_id,))
    found = {}
    for ext in installed():
        for entry in ext["snippets"]:
            if entry["language"] not in names:
                continue
            try:
                data = parse_jsonc((VSCODE_DIR / ext["id"] / entry["path"])
                                   .read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            for title, snip in data.items():
                if not isinstance(snip, dict) or "body" not in snip:
                    continue
                body = snip["body"]
                body = "\n".join(body) if isinstance(body, list) else str(body)
                prefixes = snip.get("prefix", title)
                for prefix in ([prefixes] if isinstance(prefixes, str) else prefixes):
                    found.setdefault(str(prefix), (body, snip.get("description", title)))
    return found


# ---------- Open VSX marketplace ----------

def search_open_vsx(query, category=None, size=24):
    params = {"query": query, "size": size, "sortBy": "relevance", "sortOrder": "desc"}
    if category:
        params["category"] = category
    url = OPEN_VSX + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20, context=ssl_context()) as response:
        data = json.loads(response.read().decode("utf-8"))
    results = []
    for e in data.get("extensions", []):
        download = e.get("files", {}).get("download")
        if not download:
            continue
        results.append({
            "id": f"{e.get('namespace')}.{e.get('name')}".lower(),
            "name": e.get("displayName") or e.get("name"),
            "publisher": e.get("namespace"),
            "version": e.get("version", ""),
            "description": e.get("description", ""),
            "downloads": e.get("downloadCount", 0),
            "download": download,
        })
    return results


def download_and_install(url):
    VSCODE_DIR.mkdir(parents=True, exist_ok=True)
    temp = VSCODE_DIR / "_download.vsix"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60, context=ssl_context()) as response, \
            open(temp, "wb") as f:
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > 80 * 1024 * 1024:
                raise ExtensionError("That extension is too big to download.")
            f.write(chunk)
    try:
        return install_vsix(temp)
    finally:
        temp.unlink(missing_ok=True)
