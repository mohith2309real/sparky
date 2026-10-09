# Signed update manifests.
#
# A manifest is a small JSON envelope:
#   {"schema": 1, "key": "<key id>", "signed": "<base64 payload>", "sig": "<base64 Ed25519>"}
# Only the payload inside "signed" is trusted, and only after its signature
# checks out against a key built into Sparky (keys.py).

import base64
import binascii
import json
from dataclasses import dataclass, field

from . import ed25519, versions
from .keys import TRUSTED_KEYS

CHANNELS = ("stable", "beta")


class ManifestError(Exception):
    pass


@dataclass
class Update:
    kind: str              # "pack" (code only), "full" (whole app), or "manual" (download from the site)
    version: str
    notes: str = ""
    notes_url: str = ""
    date: str = ""
    url: str = ""
    sha256: str = ""
    size: int = 0
    runtime: int = 0
    artifact: str = ""     # for full updates: mac-app-zip, windows-setup, linux-tar
    extra: dict = field(default_factory=dict)


def _b64(text, what):
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise ManifestError(f"the {what} isn't valid base64")


def read(raw, channel, keys=None):
    """Check a manifest's signature and return its payload (a dict)."""
    keys = TRUSTED_KEYS if keys is None else keys
    try:
        envelope = json.loads(raw)
    except (ValueError, TypeError):
        raise ManifestError("the update file isn't JSON")
    if not isinstance(envelope, dict) or envelope.get("schema") != 1:
        raise ManifestError("unknown update file format")
    key = keys.get(envelope.get("key"))
    if key is None:
        raise ManifestError("the update file was signed with a key Sparky doesn't know")
    payload = _b64(envelope.get("signed", ""), "payload")
    signature = _b64(envelope.get("sig", ""), "signature")
    if not ed25519.verify(_b64(key, "key"), payload, signature):
        raise ManifestError("the update file's signature is wrong")
    try:
        data = json.loads(payload)
    except ValueError:
        raise ManifestError("the signed part isn't JSON")
    if not isinstance(data, dict) or data.get("product") != "sparky":
        raise ManifestError("this update file isn't for Sparky")
    if data.get("channel") != channel:
        raise ManifestError(f"expected the {channel} channel, got {data.get('channel')!r}")
    try:
        versions.parse(data.get("version"))
    except ValueError as err:
        raise ManifestError(str(err))
    return data


def _url_ok(url):
    url = str(url)
    # https only — plain http is allowed just for a test server on this computer
    return url.startswith("https://") or url.startswith(("http://127.0.0.1:", "http://localhost:"))


def _file_ok(entry):
    return (isinstance(entry, dict) and _url_ok(entry.get("url", ""))
            and len(str(entry.get("sha256", ""))) == 64 and int(entry.get("size", 0)) > 0)


def choose(data, current, runtime, platform):
    """The best update for this copy of Sparky, or None if it's up to date."""
    latest = data["version"]
    if not versions.newer(latest, current):
        return None
    common = dict(version=latest, notes=str(data.get("notes", "")),
                  notes_url=str(data.get("notes_url", "")), date=str(data.get("date", "")))
    pack = data.get("pack")
    if platform and _file_ok(pack) and pack.get("runtime") == runtime:
        oldest = pack.get("min_version")
        if not oldest or not versions.newer(oldest, current):
            return Update(kind="pack", url=pack["url"], sha256=pack["sha256"].lower(),
                          size=int(pack["size"]), runtime=runtime, **common)
    full = (data.get("full") or {}).get(platform) if platform else None
    if _file_ok(full):
        return Update(kind="full", url=full["url"], sha256=full["sha256"].lower(),
                      size=int(full["size"]), runtime=int(data.get("runtime", 0)),
                      artifact=str(full.get("kind", "")), **common)
    return Update(kind="manual", **common)
