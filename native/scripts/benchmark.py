#!/usr/bin/env python3
"""Record measured domain performance with source and dataset hashes."""
import argparse
import datetime
import hashlib
import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshot', type=Path, default=ROOT / 'native/Caffeye/Resources/venues.json')
parser.add_argument('--output', type=Path, default=ROOT / 'native/build/benchmark.json')
args = parser.parse_args()
result = subprocess.run(['swift', 'run', '-c', 'release', '--package-path', str(ROOT / 'native/Core'),
                         'CaffeyeTools', 'benchmark', str(args.snapshot.resolve())], capture_output=True, text=True, check=True)
report = json.loads(result.stdout)
report['measuredAtUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
report['datasetSHA256'] = hashlib.sha256(args.snapshot.read_bytes()).hexdigest()
source = b''.join(p.read_bytes() for p in sorted((ROOT / 'native/Core/Sources').rglob('*.swift')))
report['benchmarkSourceSHA256'] = hashlib.sha256(source).hexdigest()
report['toolchain'] = subprocess.check_output(['swift', '--version'], text=True).strip()
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
print(args.output)
