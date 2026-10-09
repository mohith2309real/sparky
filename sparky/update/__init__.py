# Over-the-air updates: signed manifests, small code packs, full installers.
#
#   ed25519.py   checks release signatures (verification only, pure Python)
#   manifest.py  reads a signed manifest and picks the right update
#   download.py  fetches files with resume and SHA-256 checks
#   install.py   installs code packs and stages full-app updates
#   service.py   the Qt side: timers, progress, "Restart to update"
