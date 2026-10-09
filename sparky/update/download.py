# Downloading update files: resumable, cancellable, and checked against the
# size and SHA-256 from the signed manifest before anything uses them.

import hashlib
import ssl
import urllib.error
import urllib.request
from pathlib import Path

CHUNK = 64 * 1024


class DownloadError(Exception):
    pass


def ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_bytes(url, user_agent, limit=512 * 1024, timeout=20):
    """Small files (manifests). Raises DownloadError."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent,
                                                   "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as resp:
            data = resp.read(limit + 1)
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise DownloadError(f"couldn't reach the update server ({err})")
    if len(data) > limit:
        raise DownloadError("the update file is too big")
    return data


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, dest, sha256, size, user_agent, progress=None, cancelled=None, timeout=30):
    """Download url to dest (resuming a .part file), then verify it. Returns dest."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == size and sha256_of(dest) == sha256:
        return dest
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    if have >= size:
        part.unlink()
        have = 0
    headers = {"User-Agent": user_agent}
    if have:
        headers["Range"] = f"bytes={have}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as resp:
            if have and resp.status != 206:
                have = 0
            with open(part, "ab" if have else "wb") as out:
                while True:
                    if cancelled and cancelled():
                        raise DownloadError("cancelled")
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    have += len(chunk)
                    if have > size:
                        raise DownloadError("the download is bigger than expected")
                    if progress:
                        progress(have, size)
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise DownloadError(f"the download stopped ({err})")
    if have != size:
        raise DownloadError(f"the download is incomplete ({have} of {size} bytes)")
    if sha256_of(part) != sha256:
        part.unlink()
        raise DownloadError("the download doesn't match its signed checksum, so it was thrown away")
    part.replace(dest)
    return dest
