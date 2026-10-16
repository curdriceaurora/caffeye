#!/usr/bin/env python3
"""Check release prerequisites. Human review and platform acceptance remain necessary."""
import argparse
import json
import plistlib
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from audit_snapshot import audit


def evidence(value, base):
    return isinstance(value, str) and bool(value.strip()) and (base / value).is_file() and (base / value).stat().st_size > 0


def https(value):
    if not isinstance(value, str):
        return False
    url = urlparse(value)
    return url.scheme == "https" and bool(url.hostname) and not url.username and not url.password


def assess(snapshot, approval, base, app=None):
    inventory = audit(snapshot)
    checks = {
        "datasetReview": approval.get("datasetSHA256") == inventory["datasetSHA256"]
            and approval.get("redistributionReviewed") is True
            and evidence(approval.get("redistributionEvidencePath"), base),
        "privacyReview": evidence(approval.get("privacyReviewEvidencePath"), base),
        "physicalQA": evidence(approval.get("physicalQAEvidencePath"), base),
        "releaseMetadata": https(approval.get("supportURL")) and https(approval.get("privacyURL")),
        "bundleMatchesDataset": False, "privacyManifest": False, "productionSignature": False,
    }
    if app and app.is_dir():
        resource = app / "Contents/Resources" if (app / "Contents").is_dir() else app
        bundled = resource / "venues.json"
        checks["bundleMatchesDataset"] = bundled.is_file() and audit(bundled)["datasetSHA256"] == inventory["datasetSHA256"]
        manifest = resource / "PrivacyInfo.xcprivacy"
        if manifest.is_file():
            entries = plistlib.loads(manifest.read_bytes()).get("NSPrivacyAccessedAPITypes", [])
            checks["privacyManifest"] = any(e.get("NSPrivacyAccessedAPIType") == "NSPrivacyAccessedAPICategoryUserDefaults"
                and "CA92.1" in e.get("NSPrivacyAccessedAPITypeReasons", []) for e in entries)
        signature = subprocess.run(["codesign", "-dv", "--verbose=4", str(app)], capture_output=True, text=True)
        verified = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True)
        authorities = ("Authority=Developer ID Application:", "Authority=Apple Distribution:", "Authority=iPhone Distribution:")
        checks["productionSignature"] = signature.returncode == 0 and verified.returncode == 0 and any(a in signature.stderr for a in authorities)
    return {"preflightPassed": all(checks.values()), "checks": checks, "dataset": inventory,
            "scope": "Checks local prerequisites and evidence presence, not legal validity, notarization, App Store acceptance, or completeness of human QA."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--app", type=Path)
    args = parser.parse_args()
    result = assess(args.snapshot, json.loads(args.approval.read_text()), args.approval.resolve().parent, args.app)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["preflightPassed"] else 1)
