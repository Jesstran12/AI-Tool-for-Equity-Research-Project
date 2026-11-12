"""Download every document in data/raw/<TICKER>/manifest.yaml that has a url, and check its sha256.

Usage: uv run python scripts/fetch.py TICKER
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

import yaml

UA = (
    "orebody-research (academic project)"  # EDGAR rejects requests without a descriptive User-Agent
)


def main(ticker: str) -> int:
    folder = Path("data/raw") / ticker
    docs = yaml.safe_load((folder / "manifest.yaml").read_text())["documents"]
    bad = 0
    for doc in docs:
        url, want, path = doc.get("url"), doc.get("sha256"), folder / doc["file"]
        if not url:
            print(f"skip   {doc['file']} (no url)")
            continue
        if not path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r:
                path.write_bytes(r.read())
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        ok = want is None or got == want
        bad += not ok
        print(f"{'ok' if ok else 'BADSHA'} {doc['file']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1].upper()))
