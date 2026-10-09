# Shared helpers for the release scripts. Run them with a Python that has
# `cryptography` and `huggingface_hub` (BUILD_PY in scripts/release/README.md).

import base64
import hashlib
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SITES = REPO.parent / "mohith-sites"
KEY_DIR = REPO.parent / "sparky-release-signing"
KEY_ID = "sparky-2026"
HF_REPO = "mohith2309/sparky-downloads"
HF_BASE = f"https://huggingface.co/spaces/{HF_REPO}/resolve/main/"
SITE = "https://sparky-code.web.app"


def hf_token():
    """A saved Hugging Face token that can write to the downloads Space.
    The active login may be scoped to another project, so check them all
    (without switching which one is active)."""
    from huggingface_hub import HfApi, get_token
    from huggingface_hub.utils import get_stored_tokens
    owner = HF_REPO.split("/")[0]
    candidates = [get_token()] + list(get_stored_tokens().values())
    for token in dict.fromkeys(t for t in candidates if t):
        try:
            auth = HfApi(token=token).whoami().get("auth", {}).get("accessToken", {})
        except Exception:
            continue
        if auth.get("role") == "write":
            return token
        for scope in auth.get("fineGrained", {}).get("scoped", []):
            if scope.get("entity", {}).get("name") == owner and "repo.write" in scope.get("permissions", []):
                return token
    raise SystemExit(f"No saved Hugging Face token can write to {HF_REPO}.")


def version():
    text = (REPO / "sparky" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text).group(1)


def runtime():
    text = (REPO / "sparky_boot.py").read_text(encoding="utf-8")
    return int(re.search(r"^RUNTIME = (\d+)", text, re.M).group(1))


def base_version():
    text = (REPO / "sparky_boot.py").read_text(encoding="utf-8")
    return re.search(r'^BASE_VERSION = "([^"]+)"', text, re.M).group(1)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def private_key():
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    return load_pem_private_key((KEY_DIR / "sparky-release-key.pem").read_bytes(), None)


def sign(data):
    return private_key().sign(data)


def public_key_b64():
    from cryptography.hazmat.primitives import serialization
    raw = private_key().public_key().public_bytes(serialization.Encoding.Raw,
                                                  serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def envelope(payload):
    """Sign a manifest payload (dict) into the envelope Sparky reads."""
    signed = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {"schema": 1, "key": KEY_ID,
            "signed": base64.b64encode(signed).decode(),
            "sig": base64.b64encode(sign(signed)).decode()}


def run(cmd, **kwargs):
    print("$", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)
