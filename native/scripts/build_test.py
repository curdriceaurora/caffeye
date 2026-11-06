#!/usr/bin/env python3
"""Build local test ZIPs. No upload, distribution signing, or source approval is performed."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--platform", choices=["macos", "simulator", "both"], default="both")
parser.add_argument("--snapshot", type=Path, default=ROOT / "native/Caffeye/Resources/venues.json")
parser.add_argument("--output", type=Path, default=ROOT / "native/build/hardening-release")
args = parser.parse_args()
if args.output.resolve().is_relative_to(ROOT / "public"):
    parser.error("Native build artifacts must remain outside the published public/ directory")
args.output.mkdir(parents=True, exist_ok=True)
validated = subprocess.run(["swift", "run", "-c", "release", "--package-path", str(ROOT / "native/Core"),
                            "CaffeyeTools", "validate", str(args.snapshot.resolve())], capture_output=True, text=True, check=True)
metadata = {"snapshot": json.loads(validated.stdout), "localTestingOnly": True,
            "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)),
            "toolchain": subprocess.check_output(["xcodebuild", "-version"], text=True).strip(), "artifacts": {}}
for platform in (["macos", "simulator"] if args.platform == "both" else [args.platform]):
    mac = platform == "macos"
    scheme = "Caffeye-macOS" if mac else "Caffeye-iOS"
    derived = args.output / ("derived-" + platform)
    destination = "platform=macOS" if mac else "generic/platform=iOS Simulator"
    log = args.output / (platform + ".log")
    with log.open("w") as output:
        subprocess.run(["xcodebuild", "-project", str(ROOT / "native/Caffeye.xcodeproj"), "-scheme", scheme,
            "-configuration", "Release", "-destination", destination, "-derivedDataPath", str(derived),
            "CODE_SIGN_IDENTITY=-" if mac else "CODE_SIGNING_ALLOWED=NO", "build"], stdout=output, stderr=subprocess.STDOUT, check=True)
    product = derived / "Build/Products" / ("Release" if mac else "Release-iphonesimulator") / "Caffeye.app"
    folder = args.output / platform
    folder.mkdir(exist_ok=True)
    app = folder / "Caffeye.app"
    subprocess.run(["ditto", str(product), str(app)], check=True)
    resources = app / "Contents/Resources" if mac else app
    shutil.copyfile(args.snapshot, resources / "venues.json")
    if mac:
        subprocess.run(["codesign", "--force", "--sign", "-", "--entitlements", str(ROOT / "native/Caffeye/Caffeye.entitlements"), str(app)], check=True)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    archive = args.output / ("Caffeye-" + platform + ".zip")
    if archive.exists():
        archive.unlink()
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)], check=True)
    metadata["artifacts"][platform] = {"archive": str(archive), "datasetSHA256": hashlib.sha256((resources / "venues.json").read_bytes()).hexdigest(),
        "archiveSHA256": hashlib.sha256(archive.read_bytes()).hexdigest()}
(args.output / "build-info.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(args.output / "build-info.json")
