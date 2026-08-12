import argparse
import hashlib
import os
import shutil
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
target = Path(args.output)
temporary = target.with_suffix(target.suffix + ".part")
target.parent.mkdir(parents=True, exist_ok=True)
request = urllib.request.Request(args.url, headers={
    "User-Agent": "ignition-feasibility-module-fetch/1.0",
    "Referer": "https://inductiveautomation.com/downloads/third-party-modules/8.1.54",
})
try:
    with urllib.request.urlopen(request) as response, temporary.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    os.replace(temporary, target)
    print(f"{target.name} {target.stat().st_size} sha256:{digest}")
except Exception:
    temporary.unlink(missing_ok=True)
    raise
