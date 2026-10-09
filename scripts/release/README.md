# Releasing Sparky

Everything here runs with a Python that has `cryptography` and `huggingface_hub`
(for example `python3 -m venv ~/sparky-build-venv && ~/sparky-build-venv/bin/pip install
cryptography huggingface_hub pynsist`). The private signing key is read from
`../sparky-release-signing/` next to this repo. It is never committed.

- `make_pack.py OUT` builds the code pack for the current version.
- `sign_sums.py FOLDER` writes and signs `SHA256SUMS.txt` for a folder of downloads.
- `publish.py --channel beta|stable --notes notes.md [--pack] [--full FOLDER]` uploads
  files to the Hugging Face Space, signs the manifest, deploys sparky-code.web.app and
  checks the live manifest with Sparky's own verifier.

Code packs work only for apps with the same `RUNTIME` (sparky_boot.py). Bump RUNTIME,
and ship full builds, whenever Python, Qt or a bundled library changes.
