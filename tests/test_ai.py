# AI helper tests against local stand-in servers (no real API calls, no key).
# Run with: .venv/bin/python tests/test_ai.py

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sparky.ide.ai import (AIError, build_system_prompt, list_models,  # noqa: E402
                           stream_anthropic, stream_openai_compatible)

from mock_ai_server import SEEN, serve  # noqa: E402


server = serve()
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_port}"

passed = 0


def check(name, ok, detail=""):
    global passed
    assert ok, f"FAILED: {name} {detail}"
    passed += 1
    print(f"  ok - {name}")


class FakeSettings:
    def __init__(self, **values):
        self.values = values

    def value(self, key, default=None, type=None):
        return self.values.get(key, default)


# ---------- Claude via the official SDK ----------
out = []
cfg = {"name": "Anthropic (Claude)", "kind": "anthropic", "base_url": BASE,
       "key": "test-key", "model": "claude-opus-5-5"}
stream_anthropic(cfg, "SYSTEM", [{"role": "user", "content": "hi"}], out.append, lambda: False)
check("Claude reply streams in pieces", out == ["Hello ", "from ", "Claude!"], str(out))
body, headers = SEEN["body"], {k.lower(): v for k, v in SEEN["headers"].items()}
check("uses the default model claude-opus-5-5", body["model"] == "claude-opus-5-5")
check("sets effort explicitly", body.get("output_config") == {"effort": "medium"})
check("opts into server-side fallbacks", body.get("fallbacks") == "default" and
      "server-side-fallback-2026-07-01" in headers.get("anthropic-beta", ""), str(headers))
check("sends the system prompt + messages", body["system"] == "SYSTEM" and
      body["messages"] == [{"role": "user", "content": "hi"}])
check("sends the key as x-api-key", headers.get("x-api-key") == "test-key")

out = []
stream_anthropic(dict(cfg, model="claude-haiku-4-5"), "S", [{"role": "user", "content": "x"}],
                 out.append, lambda: False)
check("no effort / fallbacks for models that don't take them",
      "output_config" not in SEEN["body"] and "fallbacks" not in SEEN["body"])

try:
    stream_anthropic(dict(cfg, key="bad-key"), "S", [{"role": "user", "content": "x"}],
                     out.append, lambda: False)
    check("bad key is reported kindly", False)
except AIError as err:
    check("bad key is reported kindly", "didn't accept that API key" in str(err), str(err))

# ---------- OpenAI-compatible providers ----------
out = []
ocfg = {"name": "Ollama (on this computer)", "kind": "openai", "base_url": BASE + "/v1",
        "key": "", "model": "tiny-model"}
stream_openai_compatible(ocfg, "SYS", [{"role": "user", "content": "yo"}], out.append,
                         lambda: False)
check("OpenAI-style reply streams", "".join(out) == "Hi from OpenAI-style!")
check("system prompt goes first", SEEN["body"]["messages"][0] == {"role": "system", "content": "SYS"})
check("no Authorization header without a key", "Authorization" not in SEEN["headers"])

try:
    stream_openai_compatible(dict(ocfg, key="bad-key"), "S", [], out.append, lambda: False)
    check("bad key (OpenAI-style) is kind", False)
except AIError as err:
    check("bad key (OpenAI-style) is kind", "didn't accept that API key" in str(err))

try:
    stream_openai_compatible(dict(ocfg, base_url="http://127.0.0.1:9/v1"), "S", [],
                             out.append, lambda: False)
    check("unreachable local AI suggests starting it", False)
except AIError as err:
    check("unreachable local AI suggests starting it", "running on this computer" in str(err))

check("Load models lists the provider's models",
      list_models(ocfg) == ["big-model", "tiny-model"])

# ---------- prompts ----------
prompt = build_system_prompt(FakeSettings(ai_tutor=True, ai_instructions="Talk like a pirate."))
check("tutor mode + custom instructions in the prompt",
      "Tutor mode is on" in prompt and "Talk like a pirate." in prompt and "give back" in prompt)
prompt = build_system_prompt(FakeSettings(ai_tutor=False))
check("tutor mode can be turned off", "Tutor mode" not in prompt)

server.shutdown()
print(f"\nAll {passed} AI checks passed!")
