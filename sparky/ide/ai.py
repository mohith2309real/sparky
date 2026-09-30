# Sparky's AI helper: bring your own AI. Pick a provider in Settings → AI,
# paste your own key (stored only on this computer), choose a model, and
# add your own instructions. Claude goes through Anthropic's official SDK;
# every other provider goes through its OpenAI-compatible endpoint.

import html
import json
import re
import urllib.error
import urllib.request

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                             QTextBrowser, QVBoxLayout, QWidget)

from ..lang.parser import HELPER_WORDS, STATEMENT_WORDS
from .vscode import ssl_context

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5-5"

PROVIDERS = {
    # name: (kind, base URL, default model, needs a key)
    "Anthropic (Claude)": ("anthropic", "", ANTHROPIC_DEFAULT_MODEL, True),
    "OpenAI": ("openai", "https://api.openai.com/v1", "", True),
    "Google Gemini": ("openai", "https://generativelanguage.googleapis.com/v1beta/openai", "", True),
    "Groq": ("openai", "https://api.groq.com/openai/v1", "", True),
    "OpenRouter": ("openai", "https://openrouter.ai/api/v1", "", True),
    "Ollama (on this computer)": ("openai", "http://localhost:11434/v1", "", False),
    "LM Studio (on this computer)": ("openai", "http://localhost:1234/v1", "", False),
    "Custom (OpenAI-compatible)": ("openai", "", "", True),
}

# Claude models that take output_config.effort, and ones with server-side
# refusal fallbacks (fallbacks: "default" re-runs a declined request on the
# model Anthropic recommends for that refusal category)
EFFORT_MODELS = ("claude-fable", "claude-mythos", "claude-opus-5", "claude-sonnet-5",
                 "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-6")
FALLBACK_MODELS = {"claude-fable-5-1", "claude-fable-5", "claude-opus-5-5",
                   "claude-opus-5", "claude-sonnet-5-5"}

SPARKY_REFERENCE = f"""Sparky is an English-like language for kids. One command per line;
blocks close with `end`; comments start with #; words are not case-sensitive.
Commands: {', '.join(sorted(set(STATEMENT_WORDS) - {'end', 'else'}))}.
Helper words: {', '.join(sorted(set(HELPER_WORDS)))}.
Examples:
  say "hi " + name            ask "Your name?" into name
  set score to 0              change score by 1
  repeat 10 times ... end     repeat until score = 5 ... end     forever ... end
  if x > 3 then ... else if x = 1 then ... else ... end
  for i from 1 to 10 ... end  for each pet in pets ... end
  set pets to ["cat", "dog"]  add "fish" to pets   remove "cat" from pets
  item 1 of pets (items count from 1)   set item 2 of pets to "cow"
  teach double n / give back n * 2 / end      say double(21)    do square 50
  move 100  back 50  turn 90  turn left 45  point 0  goto 0 0  home
  pen up / pen down / pen color "blue" / pen size 5   background "ink"   clear
  hide  show  size 150  stamp  write "hi"  speed 1-10  wait 0.5
  play "pop" (pop ding boing laser drum tada jump)   play note 1-14 for 0.5
Built-in functions: length upper lower trim text number sqrt power floor ceil
  sin cos tan (degrees) min max sum join split contains pick reverse sort
  xpos() ypos() direction().  random 1 to 10, round x, abs x, x mod y.
The stage is 480x360 with (0,0) in the middle, y up; heading 0 is up and
turning right is clockwise. Colors: red orange yellow green blue purple pink
brown black white gray cyan magenta lime navy cream ink, or "#rrggbb"."""


def build_system_prompt(settings):
    parts = [
        "You are the coding helper inside Sparky, a coding app for kids and "
        "beginners. The person you're helping may be young, so be warm, "
        "encouraging and clear: short sentences, simple words, one idea at a "
        "time. When you show code, put it in a fenced code block labeled with "
        "its language (```sparky, ```python, ```javascript).",
        "They can code in Sparky, Python, JavaScript and other languages in "
        "this editor, and turn any Sparky program into Python.\n\n" + SPARKY_REFERENCE,
    ]
    if settings.value("ai_tutor", True, type=bool):
        parts.append("Tutor mode is on: help them figure it out. Explain what's "
                     "going on, point at the line that needs attention and give a "
                     "hint or a small example. Only write the whole finished "
                     "program when they have tried and ask for it directly.")
    custom = settings.value("ai_instructions", "", type=str).strip()
    if custom:
        parts.append("Their own instructions for you:\n" + custom)
    return "\n\n".join(parts)


def provider_config(settings):
    name = settings.value("ai_provider", "Anthropic (Claude)", type=str)
    kind, base, model, _ = PROVIDERS.get(name, PROVIDERS["Anthropic (Claude)"])
    return {
        "name": name,
        "kind": kind,
        "base_url": settings.value("ai_base_url", "", type=str).strip() or base,
        "key": settings.value("ai_key", "", type=str).strip(),
        "model": settings.value("ai_model", "", type=str).strip() or model,
    }


class AIError(Exception):
    pass


# ---------- Claude (official Anthropic SDK) ----------

def stream_anthropic(cfg, system, messages, on_text, cancelled):
    try:
        import anthropic
    except ImportError:
        raise AIError("Claude needs the anthropic package. Install it with: "
                      "pip install anthropic")
    client_args = {}
    if cfg["key"]:
        client_args["api_key"] = cfg["key"]
    if cfg["base_url"]:
        client_args["base_url"] = cfg["base_url"]
    client = anthropic.Anthropic(**client_args)
    model = cfg["model"] or ANTHROPIC_DEFAULT_MODEL
    request = {"model": model, "max_tokens": 16000, "system": system,
               "messages": messages}
    if model.startswith(EFFORT_MODELS):
        request["output_config"] = {"effort": "medium"}
    try:
        if model in FALLBACK_MODELS:
            stream_ctx = client.beta.messages.stream(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **request)
        else:
            stream_ctx = client.messages.stream(**request)
        with stream_ctx as stream:
            for text in stream.text_stream:
                if cancelled():
                    return
                on_text(text)
            final = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise AIError("Claude didn't accept that API key. Check it in Settings → AI.")
    except anthropic.PermissionDeniedError:
        raise AIError("That API key isn't allowed to use this model.")
    except anthropic.NotFoundError:
        raise AIError(f'Claude couldn\'t find the model "{model}". Check the model '
                      "name in Settings → AI.")
    except anthropic.RateLimitError:
        raise AIError("Too many requests right now. Wait a minute and try again.")
    except anthropic.BadRequestError as err:
        raise AIError(f"Claude couldn't do that request: {err.message}")
    except anthropic.APIStatusError as err:
        raise AIError(f"Claude had a problem ({err.status_code}). Try again soon.")
    except anthropic.APIConnectionError:
        raise AIError("I couldn't reach Claude. Check your internet connection.")
    if final.stop_reason == "refusal":
        on_text("\n\n*(Claude decided not to answer this one. Try asking in "
                "a different way.)*")
    elif final.stop_reason == "max_tokens":
        on_text("\n\n*(That answer got cut off because it was very long.)*")


# ---------- everyone else (OpenAI-compatible chat completions) ----------

def _http_error(err, cfg):
    try:
        detail = json.loads(err.read().decode("utf-8", "replace"))
        message = detail.get("error", {}).get("message") if isinstance(detail.get("error"), dict) \
            else detail.get("error") or detail.get("message")
    except (ValueError, AttributeError):
        message = None
    if err.code in (401, 403):
        return AIError(f"{cfg['name']} didn't accept that API key. Check it in Settings → AI.")
    if err.code == 404:
        return AIError(f"{cfg['name']} couldn't find that model or address. "
                       "Check the model name and URL in Settings → AI.")
    if err.code == 429:
        return AIError("Too many requests right now. Wait a minute and try again.")
    return AIError(f"{cfg['name']} had a problem ({err.code})" +
                   (f": {message}" if message else "."))


def stream_openai_compatible(cfg, system, messages, on_text, cancelled):
    if not cfg["base_url"]:
        raise AIError("Add the provider's address (base URL) in Settings → AI.")
    if not cfg["model"]:
        raise AIError("Pick a model in Settings → AI (the Load models button lists them).")
    body = {"model": cfg["model"], "stream": True,
            "messages": [{"role": "system", "content": system}] + messages}
    headers = {"Content-Type": "application/json", "User-Agent": "Sparky-IDE/2.0"}
    if cfg["key"]:
        headers["Authorization"] = f"Bearer {cfg['key']}"
    request = urllib.request.Request(cfg["base_url"].rstrip("/") + "/chat/completions",
                                     data=json.dumps(body).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=180, context=ssl_context()) as response:
            for raw in response:
                if cancelled():
                    return
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except ValueError:
                    continue
                choices = chunk.get("choices") or [{}]
                text = (choices[0].get("delta") or {}).get("content")
                if text:
                    on_text(text)
    except urllib.error.HTTPError as err:
        raise _http_error(err, cfg)
    except urllib.error.URLError:
        local = "localhost" in cfg["base_url"] or "127.0.0.1" in cfg["base_url"]
        raise AIError(f"I couldn't reach {cfg['name']}." +
                      (" Is it running on this computer?" if local
                       else " Check your internet connection and the base URL."))


def list_models(cfg):
    """Model names the provider offers (for the Load models button)."""
    if cfg["kind"] == "anthropic":
        try:
            import anthropic
        except ImportError:
            raise AIError("Claude needs the anthropic package.")
        args = {"api_key": cfg["key"]} if cfg["key"] else {}
        if cfg["base_url"]:
            args["base_url"] = cfg["base_url"]
        try:
            return [m.id for m in anthropic.Anthropic(**args).models.list()]
        except anthropic.AuthenticationError:
            raise AIError("Claude didn't accept that API key.")
        except anthropic.APIConnectionError:
            raise AIError("I couldn't reach Claude.")
        except anthropic.APIStatusError as err:
            raise AIError(f"Claude had a problem ({err.status_code}).")
    headers = {"User-Agent": "Sparky-IDE/2.0"}
    if cfg["key"]:
        headers["Authorization"] = f"Bearer {cfg['key']}"
    request = urllib.request.Request(cfg["base_url"].rstrip("/") + "/models", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl_context()) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raise _http_error(err, cfg)
    except urllib.error.URLError:
        raise AIError(f"I couldn't reach {cfg['name']}.")
    return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))


class AIWorker(QThread):
    chunk = pyqtSignal(str)
    failed = pyqtSignal(str)
    done = pyqtSignal()

    def __init__(self, cfg, system, messages, parent=None):
        super().__init__(parent)
        self.cfg, self.system, self.messages = cfg, system, messages
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        stream = stream_anthropic if self.cfg["kind"] == "anthropic" \
            else stream_openai_compatible
        try:
            stream(self.cfg, self.system, self.messages, self.chunk.emit,
                   lambda: self._cancel)
        except AIError as err:
            self.failed.emit(str(err))
        except Exception as err:  # never crash the IDE over a network hiccup
            self.failed.emit(f"Something went wrong talking to the AI: {err}")
        self.done.emit()


class ModelsWorker(QThread):
    loaded = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg

    def run(self):
        try:
            self.loaded.emit(list_models(self.cfg))
        except AIError as err:
            self.failed.emit(str(err))
        except Exception as err:
            self.failed.emit(str(err))


# ---------- chat panel ----------

CODE_BLOCK = re.compile(r"```([\w+-]*)[^\n]*\n(.*?)```", re.S)


def markdown_html(text, palette):
    """Tiny markdown: fenced code, inline code, bold, italics, line breaks."""
    blocks, out, pos = [], [], 0
    for m in CODE_BLOCK.finditer(text):
        out.append(("text", text[pos:m.start()]))
        out.append(("code", m.group(2)))
        pos = m.end()
    tail = text[pos:]
    if "```" in tail:   # still streaming a code block
        before, _, code = tail.partition("```")
        out.append(("text", before))
        out.append(("code", code.split("\n", 1)[1] if "\n" in code else ""))
    else:
        out.append(("text", tail))
    for kind, chunk in out:
        if kind == "code":
            blocks.append(
                f'<pre style="background:{palette["panel2"]};color:{palette["text"]};'
                f'padding:8px;border-radius:6px;font-family:Menlo,Consolas,monospace;'
                f'font-size:12px;white-space:pre-wrap">{html.escape(chunk.rstrip())}</pre>')
            continue
        t = html.escape(chunk)
        t = re.sub(r"`([^`\n]+)`", lambda m: f'<code style="background:{palette["panel2"]}">'
                   f"{m.group(1)}</code>", t)
        t = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<i>\1</i>", t)
        blocks.append(t.strip("\n").replace("\n", "<br>"))
    return "".join(b for b in blocks if b)


def last_code_block(text):
    matches = CODE_BLOCK.findall(text)
    return matches[-1] if matches else None


class AIPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.history = []           # [{"role", "content"}] shown in the chat
        self.worker = None
        self.reply = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("AI HELPER")
        title.setObjectName("SectionTitle")
        top.addWidget(title)
        top.addStretch(1)
        new_chat = QPushButton("New chat")
        new_chat.setObjectName("GhostButton")
        new_chat.clicked.connect(self.new_chat)
        top.addWidget(new_chat)
        setup = QPushButton("⚙")
        setup.setObjectName("GhostButton")
        setup.setToolTip("Choose your AI provider, key and model")
        setup.clicked.connect(lambda: self.main.open_settings("AI"))
        top.addWidget(setup)
        layout.addLayout(top)

        self.who = QLabel()
        self.who.setObjectName("FileLabel")
        self.who.setWordWrap(True)
        layout.addWidget(self.who)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        layout.addWidget(self.view, 1)

        quick = QHBoxLayout()
        for label, prompt in (("Explain", "Explain what my code does, step by step."),
                              ("Fix my error", "My program has a problem. Help me find and fix it."),
                              ("Idea", "Give me one fun idea to add to this program.")):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, p=prompt: self.ask(p))
            quick.addWidget(b)
        layout.addLayout(quick)

        self.input = QPlainTextEdit()
        self.input.setObjectName("AskBox")
        self.input.setPlaceholderText("Ask anything about your code…  (Enter sends, "
                                      "Shift+Enter makes a new line)")
        self.input.setFixedHeight(76)
        self.input.installEventFilter(self)
        layout.addWidget(self.input)

        row = QHBoxLayout()
        self.insert_btn = QPushButton("⤵ Insert code")
        self.insert_btn.setToolTip("Put the last code the AI wrote into your editor")
        self.insert_btn.clicked.connect(self.insert_code)
        self.insert_btn.setEnabled(False)
        row.addWidget(self.insert_btn)
        row.addStretch(1)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("RunButton")
        self.send_btn.clicked.connect(lambda: self.ask(self.input.toPlainText()))
        row.addWidget(self.send_btn)
        layout.addLayout(row)
        self.refresh_header()
        self.render()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.input and event.type() == QEvent.Type.KeyPress and \
                event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and \
                not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.ask(self.input.toPlainText())
            return True
        return super().eventFilter(obj, event)

    def refresh_header(self):
        cfg = provider_config(self.main.settings)
        ready = cfg["kind"] == "anthropic" or bool(cfg["model"])
        self.who.setText(f"{cfg['name']} · {cfg['model'] or 'no model chosen yet'}"
                         + ("" if ready else " — press ⚙ to set up"))

    def new_chat(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        self.history = []
        self.reply = ""
        self.insert_btn.setEnabled(False)
        self.render()

    def render(self):
        p = self.main.palette_colors
        if not self.history and not self.reply:
            self.view.setHtml(
                f'<p style="color:{p["muted"]}">Ask about your code, get a hint when '
                "you're stuck, or ask for an idea. The AI sees the file you have open.</p>"
                f'<p style="color:{p["muted"]}">Set up your own AI with ⚙: Claude, '
                "OpenAI, Gemini, Groq, OpenRouter, or a model on this computer with "
                "Ollama or LM Studio.</p>")
            return
        parts = []
        for msg in self.history:
            if msg["role"] == "user":
                parts.append(f'<p style="margin:10px 0 2px;color:{p["accent2"]}"><b>You</b></p>'
                             f"<div>{html.escape(msg['shown']).replace(chr(10), '<br>')}</div>")
            else:
                parts.append(f'<p style="margin:10px 0 2px;color:{p["accent"]}"><b>AI</b></p>'
                             f"<div>{markdown_html(msg['content'], p)}</div>")
        if self.reply:
            parts.append(f'<p style="margin:10px 0 2px;color:{p["accent"]}"><b>AI</b></p>'
                         f"<div>{markdown_html(self.reply, p)}</div>")
        self.view.setHtml("".join(parts))
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def context_text(self):
        editor = self.main.editor
        code = editor.toPlainText()
        if len(code) > 60000:
            code = code[:60000] + "\n… (the rest of the file is cut off)"
        text = (f"[My open file: {editor.display_name()} ({editor.language.name})]\n"
                f"```{editor.language.id}\n{code}\n```")
        if self.main.last_error:
            text += f"\n[The last error I got: {self.main.last_error}]"
        return text

    def ask(self, question):
        question = question.strip()
        if not question or (self.worker and self.worker.isRunning()):
            return
        self.input.clear()
        self.history.append({"role": "user", "content": question, "shown": question})
        # only the newest question carries the code, so the chat stays small
        messages = [{"role": m["role"], "content": m["content"]} for m in self.history[:-1]]
        messages.append({"role": "user",
                         "content": question + "\n\n" + self.context_text()})
        cfg = provider_config(self.main.settings)
        self.reply = ""
        self.render()
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Thinking…")
        self.worker = AIWorker(cfg, build_system_prompt(self.main.settings), messages, self)
        self.worker.chunk.connect(self.on_chunk)
        self.worker.failed.connect(self.on_failed)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    def on_chunk(self, text):
        self.reply += text
        self.render()

    def on_failed(self, message):
        self.reply += f"\n\n⚠️ {message}"
        self.render()

    def on_done(self):
        if self.reply:
            self.history.append({"role": "assistant", "content": self.reply})
        self.reply = ""
        self.render()
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        last = next((m["content"] for m in reversed(self.history)
                     if m["role"] == "assistant"), "")
        self.insert_btn.setEnabled(last_code_block(last) is not None)

    def insert_code(self):
        last = next((m["content"] for m in reversed(self.history)
                     if m["role"] == "assistant"), "")
        found = last_code_block(last)
        if found:
            lang, code = found
            self.main.insert_ai_code(lang.lower(), code.rstrip("\n"))

    def apply_palette(self):
        self.render()
