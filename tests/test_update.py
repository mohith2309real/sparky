# Over-the-air update tests: signatures, versions, manifests, downloads,
# code packs and the boot loader's rollback. No Qt, no network (a local
# HTTP server stands in for Hugging Face). Run with:
#   python3 tests/test_update.py

import base64
import hashlib
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "release"))

import sparky  # noqa: E402
import sparky_boot  # noqa: E402
from sparky.update import download, ed25519, install, manifest, versions, where  # noqa: E402

passed = 0


def check(label, ok):
    global passed
    if not ok:
        raise SystemExit(f"FAILED: {label}")
    passed += 1


# ---------- a tiny Ed25519 signer, for tests only (RFC 8032 section 6) ----------

def _compress(point):
    zinv = pow(point[2], ed25519._P - 2, ed25519._P)
    x = point[0] * zinv % ed25519._P
    y = point[1] * zinv % ed25519._P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _expand(secret):
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_of(secret):
    return _compress(ed25519._mul(_expand(secret)[0], ed25519._BASE))


def sign(secret, message):
    a, prefix = _expand(secret)
    public = public_of(secret)
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % ed25519._L
    r_bytes = _compress(ed25519._mul(r, ed25519._BASE))
    h = int.from_bytes(hashlib.sha512(r_bytes + public + message).digest(), "little") % ed25519._L
    return r_bytes + ((r + h * a) % ed25519._L).to_bytes(32, "little")


SECRET = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
check("test signer makes the RFC public key", public_of(SECRET).hex() ==
      "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
check("test signer makes the RFC signature", sign(SECRET, b"").hex() ==
      "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
TEST_KEYS = {"test": base64.b64encode(public_of(SECRET)).decode()}


def envelope(payload, secret=SECRET, key="test"):
    signed = json.dumps(payload).encode()
    return json.dumps({"schema": 1, "key": key, "signed": base64.b64encode(signed).decode(),
                       "sig": base64.b64encode(sign(secret, signed)).decode()}).encode()


# ---------- signatures ----------

vectors = [
    ("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]
for pk, msg, sig in vectors:
    check(f"RFC vector {pk[:8]}", ed25519.verify(bytes.fromhex(pk), bytes.fromhex(msg), bytes.fromhex(sig)))
    check(f"RFC vector {pk[:8]} rejects a changed message",
          not ed25519.verify(bytes.fromhex(pk), bytes.fromhex(msg) + b"!", bytes.fromhex(sig)))
good = sign(SECRET, b"hello")
check("own signature verifies", ed25519.verify(public_of(SECRET), b"hello", good))
check("flipped bit fails", not ed25519.verify(public_of(SECRET), b"hello", good[:5] + bytes([good[5] ^ 1]) + good[6:]))
check("short key fails", not ed25519.verify(public_of(SECRET)[:31], b"hello", good))
check("non-bytes fails", not ed25519.verify("abc", b"hello", good))
check("Sparky's real key is 32 bytes", all(len(base64.b64decode(k)) == 32
                                           for k in manifest.TRUSTED_KEYS.values()))

# ---------- versions ----------

order = ["2.0.0", "3.0.0-alpha.1", "3.0.0-alpha.2", "3.0.0-alpha.10", "3.0.0-beta.1",
         "3.0.0-rc.1", "3.0.0", "3.0.1", "3.1", "3.1.1", "10.0.0"]
check("versions sort", sorted(order, key=versions.parse) == order)
check("newer", versions.newer("3.0.0", "3.0.0-rc.1") and not versions.newer("3.0.0", "3.0.0"))
check("prerelease", versions.is_prerelease("3.0.0-alpha.1") and not versions.is_prerelease("3.0.0"))
try:
    versions.parse("3.0.0-banana")
    check("bad version rejected", False)
except ValueError:
    check("bad version rejected", True)
check("boot loader orders versions the same way",
      all(sparky_boot._newer(b, a) for a, b in zip(order, order[1:])))
check("built-in code version matches the boot loader", sparky.__version__ == sparky_boot.BASE_VERSION)
check("where.data_dir matches the boot loader", where.data_dir() == sparky_boot.data_dir())

# ---------- manifests ----------

FILE = {"url": "https://example.com/a.zip", "sha256": "a" * 64, "size": 10}
payload = {"product": "sparky", "channel": "beta", "version": "3.0.1", "notes": "Fixes",
           "runtime": 1, "pack": dict(FILE, runtime=1),
           "full": {"mac-arm64": dict(FILE, kind="mac-app-zip")}}
data = manifest.read(envelope(payload), "beta", TEST_KEYS)
check("manifest reads", data["version"] == "3.0.1")
for label, raw, channel in [
    ("wrong channel", envelope(payload), "stable"),
    ("unknown key", envelope(payload, key="nope"), "beta"),
    ("wrong product", envelope(dict(payload, product="other")), "beta"),
    ("bad version", envelope(dict(payload, version="soon")), "beta"),
    ("not json", b"<html>", "beta"),
]:
    try:
        manifest.read(raw, channel, TEST_KEYS)
        check(f"manifest rejects {label}", False)
    except manifest.ManifestError:
        check(f"manifest rejects {label}", True)
tampered = json.loads(envelope(payload))
tampered["signed"] = base64.b64encode(json.dumps(dict(payload, version="9.9.9")).encode()).decode()
try:
    manifest.read(json.dumps(tampered).encode(), "beta", TEST_KEYS)
    check("manifest rejects a changed payload", False)
except manifest.ManifestError:
    check("manifest rejects a changed payload", True)
try:
    manifest.read(envelope(payload, secret=b"\1" * 32), "beta", TEST_KEYS)
    check("manifest rejects someone else's signature", False)
except manifest.ManifestError:
    check("manifest rejects someone else's signature", True)

pick = manifest.choose(data, "3.0.0", 1, "mac-arm64")
check("same runtime gets a code pack", pick.kind == "pack" and pick.version == "3.0.1")
check("new runtime gets the full app", manifest.choose(data, "3.0.0", 2, "mac-arm64").kind == "full")
check("full update for unknown platform is manual", manifest.choose(data, "3.0.0", 2, "linux-arm64").kind == "manual")
check("up to date gives nothing", manifest.choose(data, "3.0.1", 1, "mac-arm64") is None)
check("newer installed gives nothing", manifest.choose(data, "3.1.0", 1, "mac-arm64") is None)
check("source runs never get packs", manifest.choose(data, "3.0.0", 1, None).kind == "manual")
too_old = dict(payload, pack=dict(FILE, runtime=1, min_version="3.0.1"))
check("min_version respected", manifest.choose(too_old, "3.0.0", 1, "mac-arm64").kind == "full")
http_url = dict(payload, pack=dict(FILE, runtime=1, url="http://example.com/a.zip"), full={})
check("plain http URLs are ignored", manifest.choose(http_url, "3.0.0", 1, "mac-arm64").kind == "manual")

# ---------- downloads (local server with Range support) ----------

blob = os.urandom(300_000)
blob_sha = hashlib.sha256(blob).hexdigest()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body, status = blob, 200
        rng = self.headers.get("Range")
        if rng:
            start = int(rng.split("=")[1].split("-")[0])
            body, status = blob[start:], 206
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_address[1]}/pack.zip"
tmp = Path(tempfile.mkdtemp())
seen = []
out = download.download(url, tmp / "a.bin", blob_sha, len(blob), "test", progress=lambda d, t: seen.append(d))
check("download completes", out.read_bytes() == blob and seen[-1] == len(blob))
(tmp / "b.bin.part").write_bytes(blob[:100_000])
out = download.download(url, tmp / "b.bin", blob_sha, len(blob), "test")
check("download resumes a partial file", out.read_bytes() == blob)
try:
    download.download(url, tmp / "c.bin", "0" * 64, len(blob), "test")
    check("checksum mismatch rejected", False)
except download.DownloadError:
    check("checksum mismatch rejected", not (tmp / "c.bin").exists() and not (tmp / "c.bin.part").exists())
try:
    download.download(url, tmp / "d.bin", blob_sha, len(blob), "test", cancelled=lambda: True)
    check("cancel works", False)
except download.DownloadError:
    check("cancel works", True)
server.shutdown()

# ---------- code packs + the boot loader ----------

import make_pack  # noqa: E402

pack_dir = tmp / "packs-out"
real_version = sparky.__version__
pack_zip = make_pack.build(pack_dir)
listing = json.loads(zipfile.ZipFile(pack_zip).read("pack-files.json"))
check("pack lists the sparky package", "sparky/__init__.py" in listing["files"])
check("pack leaves out caches", not any("__pycache__" in f for f in listing["files"]))
check("pack is reproducible", hashlib.sha256(pack_zip.read_bytes()).hexdigest() ==
      hashlib.sha256(make_pack.build(tmp / "again").read_bytes()).hexdigest())


def make_test_pack(version, runtime=1):
    """A pack zip whose sparky/__init__.py says `version`."""
    target = tmp / f"pack-{version}.zip"
    files = {}
    with zipfile.ZipFile(pack_zip) as src, zipfile.ZipFile(target, "w") as dst:
        for name in src.namelist():
            if name == "pack-files.json":
                continue
            content = src.read(name)
            if name == "sparky/__init__.py":
                content = content.replace(real_version.encode(), version.encode())
            files[name] = hashlib.sha256(content).hexdigest()
            dst.writestr(name, content)
        dst.writestr("pack-files.json", json.dumps({"version": version, "runtime": runtime,
                                                    "files": files}))
    return target


updates = tmp / "data" / "updates"
sparky_boot.data_dir = lambda: tmp / "data"
newer_version = "9.0.0"
install.install_pack(make_test_pack(newer_version), newer_version, 1, "x" * 64, root=updates)
state = install.load_state(updates)
check("pack becomes current", state["current"] == newer_version)
check("pack folder has pack.json", (updates / "packs" / newer_version / "pack.json").exists())
folder, version = sparky_boot.choose_pack()
check("boot loader picks the pack", version == newer_version and folder.name == newer_version)

try:
    install.install_pack(make_test_pack("9.0.1", runtime=7), "9.0.1", 1, "x" * 64, root=updates)
    check("pack for another runtime refused", False)
except install.InstallError:
    check("pack for another runtime refused", install.load_state(updates)["current"] == newer_version)

evil = tmp / "evil.zip"
with zipfile.ZipFile(evil, "w") as z:
    z.writestr("../outside.txt", "nope")
try:
    install.install_pack(evil, "9.0.2", 1, "x" * 64, root=updates)
    check("zip with ../ refused", False)
except install.InstallError:
    check("zip with ../ refused", not (updates / "outside.txt").exists())

install.install_pack(make_test_pack("9.1.0"), "9.1.0", 1, "x" * 64, root=updates)
state = install.load_state(updates)
check("previous version remembered", state["previous"] == newer_version and state["current"] == "9.1.0")

# a pack that keeps failing to start falls back to the previous one
(updates / "booting.json").write_text(json.dumps({"version": "9.1.0", "tries": 2}))
folder, version = sparky_boot.choose_pack()
check("failed pack rolls back", version == newer_version and "9.1.0" in install.load_state(updates)["bad"])
check("rollback explains itself", "9.1.0" in sparky_boot.notice and newer_version in sparky_boot.notice)

# a damaged pack is refused, and with nothing left Sparky uses its built-in code
victim = updates / "packs" / newer_version / "sparky" / "__init__.py"
victim.write_text(victim.read_text() + "\n# changed\n")
folder, version = sparky_boot.choose_pack()
check("damaged pack refused", folder is None and newer_version in install.load_state(updates)["bad"])
check("damage explained", "damaged" in sparky_boot.notice)

# mark_good clears the start marker
(updates / "booting.json").write_text(json.dumps({"version": "x", "tries": 1}))
sparky_boot.mark_good()
check("mark_good clears the marker", not (updates / "booting.json").exists())

# packs older than the built-in code are ignored
install.install_pack(make_test_pack("1.0.0"), "1.0.0", 1, "x" * 64, root=updates)
check("old pack ignored", sparky_boot.choose_pack() == (None, None))
install.prune(updates, keep={"1.0.0"})
check("prune removes old packs", [p.name for p in (updates / "packs").iterdir()] == ["1.0.0"])

shutil.rmtree(tmp, ignore_errors=True)
print(f"\nAll {passed} update checks passed!")
