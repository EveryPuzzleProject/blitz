"""Screenshot Wayback Machine captures with headless Chrome.

    python docs/lost/shoot.py <label> <timestamp|live> <url> [--tall]

Writes docs/lost/shots/<label>.png. A timestamp is a Wayback one (YYYYMMDD or
YYYYMMDDhhmmss; the nearest capture is used); "live" shoots the URL as it is today.
The Wayback toolbar is kept on purpose: it is the provenance (archive.org, the date).
"""
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUT = Path(__file__).parent / "shots"


def shoot(label, ts, url, tall=False):
    OUT.mkdir(exist_ok=True)
    target = url if ts == "live" else f"https://web.archive.org/web/{ts}/{url}"
    png = OUT / f"{label}.png"
    size = "1280,2000" if tall else "1280,1000"
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check",
        f"--window-size={size}", "--timeout=60000", "--virtual-time-budget=20000",
        f"--user-data-dir={Path(tempfile.gettempdir()) / 'blitz-shoot-profile'}",
        f"--screenshot={png}", target,
    ], check=True, capture_output=True, timeout=120)
    print(png, "<-", target)
    return png


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--tall"]
    shoot(*args[:3], tall="--tall" in sys.argv)
