# Version numbers like 3.0.0, 3.0.1, 3.0.0-alpha.2, 3.0.0-beta.1, 3.0.0-rc.1.
# A final release is newer than any of its pre-releases.

import re

_PRE_RANK = {"alpha": 0, "beta": 1, "rc": 2}
_PATTERN = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:-(alpha|beta|rc)(?:\.(\d+))?)?$")


def parse(text):
    """'3.0.0-alpha.2' -> (3, 0, 0, 0, 2). Raises ValueError for anything else."""
    match = _PATTERN.match(str(text).strip())
    if not match:
        raise ValueError(f"not a Sparky version: {text!r}")
    major, minor, patch, pre, num = match.groups()
    rank = _PRE_RANK[pre] if pre else 3
    return int(major), int(minor), int(patch or 0), rank, int(num or 0)


def newer(a, b):
    """True if version a is newer than version b."""
    return parse(a) > parse(b)


def is_prerelease(text):
    return parse(text)[3] < 3
