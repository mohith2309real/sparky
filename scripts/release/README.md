# Releasing Sparky

Everything here runs with a Python that has `cryptography` and `huggingface_hub`
(for example `python3 -m venv ~/sparky-build-venv && ~/sparky-build-venv/bin/pip install
cryptography huggingface_hub pynsist dmgbuild`). The private signing key is read from
`../sparky-release-signing/` next to this repo. It is never committed.

- `make_pack.py OUT` builds the code pack for the current version.
- `sign_sums.py FOLDER` writes and signs `SHA256SUMS.txt` for a folder of downloads.
- `publish.py --channel beta|stable --notes notes.md [--pack] [--full FOLDER]` uploads
  files to the Hugging Face Space, signs the manifest, deploys sparky-code.web.app and
  checks the live manifest with Sparky's own verifier.

Code packs work only for apps with the same `RUNTIME` (sparky_boot.py). Bump RUNTIME,
and ship full builds, whenever Python, Qt or a bundled library changes.

Final releases also run `make_feeds.py`, `make_web_docs.py` and `make_site_pages.py`.
The generated site keeps the existing Firebase target. `export_design.py` exports
the native design tokens. Installer artwork comes from `make_installer_art.py`.
`make_dmg.py` uses build-only dmgbuild to write the Finder layout without UI scripting.

Full publish includes the DMG, portable Windows ZIP and signed checksum files.
Keep older outputs in `build/archive`; never put signing material in build inputs.
