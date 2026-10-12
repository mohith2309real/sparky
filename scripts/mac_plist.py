# Finish the Mac app's Info.plist after PyInstaller: the real version, an
# owner for .spark files, and a copyright line. Then re-sign the bundle
# (ad-hoc), since changing the plist breaks PyInstaller's signature.
#   python scripts/mac_plist.py dist/Sparky.app

import plistlib
import re
import subprocess
import sys
from pathlib import Path

app = Path(sys.argv[1])
version = re.search(r'__version__ = "([^"]+)"',
                    (Path(__file__).resolve().parents[1] / "sparky" / "__init__.py").read_text()).group(1)
match = re.match(r"(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$", version)
major, minor, patch, pre, num = match.groups()
build = {"alpha": 0, "beta": 100, "rc": 200, None: 999}[pre] + int(num or 0)

path = app / "Contents" / "Info.plist"
info = plistlib.loads(path.read_bytes())
icon = info.get("CFBundleIconFile", "Sparky.icns")
info.update({
    "CFBundleShortVersionString": version,
    "CFBundleVersion": f"{major}.{minor}.{patch}.{build}",
    "NSHumanReadableCopyright": "Sparky — made by Mohith · sparky-code.web.app",
    "LSApplicationCategoryType": "public.app-category.education",
    "CFBundleDocumentTypes": [{
        "CFBundleTypeName": "Sparky program",
        "CFBundleTypeRole": "Editor",
        "LSHandlerRank": "Owner",
        "CFBundleTypeExtensions": ["spark"],
        "CFBundleTypeIconFile": icon,
        "LSItemContentTypes": ["io.github.mohith2309.sparky.program"],
    }],
    "UTExportedTypeDeclarations": [{
        "UTTypeIdentifier": "io.github.mohith2309.sparky.program",
        "UTTypeDescription": "Sparky program",
        "UTTypeConformsTo": ["public.plain-text"],
        "UTTypeIconFile": icon,
        "UTTypeTagSpecification": {"public.filename-extension": ["spark"]},
    }],
})
for extension,label,conforms in [('sparky','Sparky project','public.zip-archive'),('sparkytask','Sparky assignment','public.json')]:
    uti='io.github.mohith2309.sparky.'+extension
    info['CFBundleDocumentTypes'].append({'CFBundleTypeName':label,'CFBundleTypeRole':'Editor','LSHandlerRank':'Owner','CFBundleTypeExtensions':[extension],'CFBundleTypeIconFile':icon,'LSItemContentTypes':[uti]})
    info['UTExportedTypeDeclarations'].append({'UTTypeIdentifier':uti,'UTTypeDescription':label,'UTTypeConformsTo':[conforms],'UTTypeTagSpecification':{'public.filename-extension':[extension]}})
path.write_bytes(plistlib.dumps(info))
subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
print(f"Info.plist: {version} ({info['CFBundleVersion']}), .spark files, re-signed")
