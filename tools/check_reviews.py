"""Check every review in a publication repo: valid JSON, the expected keys, and
only ocr.json and review.json in each puzzle folder. Exits 1 on any problem.

    python tools/check_reviews.py [publication repo]    (default: the current folder)
"""
import json
import sys
from pathlib import Path

problems = []
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
for folder in sorted((root / "reviews").glob("*")):
    if not folder.is_dir():
        continue
    extra = {p.name for p in folder.iterdir()} - {"ocr.json", "review.json"}
    if extra:
        problems.append(f"{folder}: unexpected files {sorted(extra)}")
    f = folder / "review.json"
    if not f.exists():
        continue
    try:
        rv = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        problems.append(f"{f}: not valid JSON ({e})")
        continue
    if not isinstance(rv, dict) or not isinstance(rv.get("ready"), bool):
        problems.append(f"{f}: needs \"ready\": true or false")
    for key in ("corrections", "sic", "regions", "unsure"):
        if key in rv and not isinstance(rv[key], dict):
            problems.append(f"{f}: \"{key}\" must be an object")
    if "confirm" in rv and not isinstance(rv["confirm"], list):
        problems.append(f"{f}: \"confirm\" must be a list")

print("\n".join(problems) or "All reviews look well-formed.")
sys.exit(1 if problems else 0)
