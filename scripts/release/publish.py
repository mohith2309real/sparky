# Publish a Sparky release to an update channel.
#
#   publish.py --channel beta --notes notes.md --pack
#   publish.py --channel stable --notes notes.md --pack --full build/release
#
# 1. builds the code pack (--pack) and uploads it to the Hugging Face Space
# 2. uploads full-app files from a folder (--full), if given
# 3. writes the signed manifest to mohith-sites/sparky/updates/<channel>.json
# 4. deploys sparky-code.web.app and checks the live manifest with Sparky's
#    own verifier, exactly as an installed app would
# --dry-run stops after writing the manifest.

import argparse
import datetime
import json
import sys
import urllib.request
from pathlib import Path

from common import (HF_BASE, HF_REPO, REPO, SITE, SITES, envelope, run, runtime,
                    sha256, version)
import make_pack

FULL_KINDS = {
    "Sparky-mac-arm64.zip": ("mac-arm64", "mac-app-zip"),
    "Sparky-Setup.exe": ("windows-x64", "windows-setup"),
    "Sparky-Linux-x86_64.tar.gz": ("linux-x86_64", "linux-tar"),
    "Sparky-Linux-arm64.tar.gz": ("linux-arm64", "linux-tar"),
}


def upload(local, remote):
    from huggingface_hub import HfApi
    HfApi().upload_file(path_or_fileobj=str(local), path_in_repo=remote, repo_id=HF_REPO,
                        repo_type="space", commit_message=f"Sparky {version()}: {remote}")
    return HF_BASE + remote


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=["stable", "beta"], required=True)
    parser.add_argument("--notes", required=True, help="markdown file with the release notes")
    parser.add_argument("--pack", action="store_true")
    parser.add_argument("--full", help="folder with full-app files to publish")
    parser.add_argument("--min-version", help="oldest version allowed to take the pack")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ver = version()
    payload = {"product": "sparky", "channel": args.channel, "version": ver,
               "date": datetime.date.today().isoformat(),
               "notes": Path(args.notes).read_text(encoding="utf-8").strip(),
               "notes_url": f"{SITE}/releases.html#v{ver}", "runtime": runtime()}
    if args.pack:
        pack = make_pack.build(REPO / "build" / "release" / "packs")
        url = HF_BASE + f"updates/{ver}/{pack.name}"
        if not args.dry_run:
            url = upload(pack, f"updates/{ver}/{pack.name}")
        payload["pack"] = {"runtime": runtime(), "url": url, "sha256": sha256(pack),
                           "size": pack.stat().st_size}
        if args.min_version:
            payload["pack"]["min_version"] = args.min_version
    if args.full:
        full = {}
        for path in sorted(Path(args.full).iterdir()):
            if path.name not in FULL_KINDS:
                continue
            platform, kind = FULL_KINDS[path.name]
            # stable replaces the website's downloads; beta files go in their own folder
            remote = (f"download/{path.name}" if args.channel == "stable"
                      else f"beta/{ver}/{path.name}")
            url = HF_BASE + remote
            if not args.dry_run:
                url = upload(path, remote)
            full[platform] = {"url": url, "sha256": sha256(path),
                              "size": path.stat().st_size, "kind": kind}
        payload["full"] = full
    target = SITES / "sparky" / "updates" / f"{args.channel}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(envelope(payload), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    if args.dry_run:
        return
    run(["firebase", "deploy", "--only", "hosting:sparky", "--non-interactive"], cwd=SITES)

    sys.path.insert(0, str(REPO))
    from sparky.update import manifest
    live = f"{SITE}/updates/{args.channel}.json?check={datetime.datetime.now().timestamp()}"
    raw = urllib.request.urlopen(live, timeout=30).read()
    data = manifest.read(raw, args.channel)
    assert data["version"] == ver, data["version"]
    print(f"live {args.channel} manifest verified: Sparky {data['version']}")


if __name__ == "__main__":
    main()
