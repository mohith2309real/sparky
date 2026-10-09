# Write SHA256SUMS.txt for every file in a folder, plus SHA256SUMS.txt.sig:
# a raw 64-byte Ed25519 signature that OpenSSL can check:
#   openssl pkeyutl -verify -pubin -inkey release-key.pem -rawin \
#       -in SHA256SUMS.txt -sigfile SHA256SUMS.txt.sig

import sys
from pathlib import Path

from common import sha256, sign


def sign_folder(folder):
    folder = Path(folder)
    names = sorted(p.name for p in folder.iterdir()
                   if p.is_file() and not p.name.startswith(("SHA256SUMS", ".")))
    sums = "".join(f"{sha256(folder / n)}  {n}\n" for n in names).encode()
    (folder / "SHA256SUMS.txt").write_bytes(sums)
    (folder / "SHA256SUMS.txt.sig").write_bytes(sign(sums))
    print(f"signed {len(names)} files in {folder}")


if __name__ == "__main__":
    sign_folder(sys.argv[1])
