#!/usr/bin/env python3
"""Download MostlyMusic video files using 10 parallel workers.

Usage:
    python download_videos.py [output_dir]

Default output dir: ./videos/
Skips files already downloaded.
"""
import sys
import os
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

URLS_FILE = Path(__file__).parent / "video_urls.txt"
OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "videos"
WORKERS = 6  # fewer workers for large video files

OUT_DIR.mkdir(parents=True, exist_ok=True)

def fname_from_url(url: str) -> str:
    path = url.split("?")[0].split("/")
    # Use last two path components: hash/hash.quality.mp4
    return path[-1]

def download_one(url: str) -> tuple[str, str]:
    fname = fname_from_url(url)
    dest = OUT_DIR / fname
    if dest.exists() and dest.stat().st_size > 10_000:
        return fname, "skip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
            while chunk := resp.read(65536):
                f.write(chunk)
        return fname, "ok"
    except Exception as e:
        if dest.exists():
            dest.unlink()
        return fname, f"fail:{e}"

urls = [u.strip() for u in URLS_FILE.read_text().splitlines() if u.strip()]
print(f"Downloading {len(urls)} videos to {OUT_DIR}/")

ok = skip = fail = 0
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    futures = {pool.submit(download_one, u): u for u in urls}
    for i, fut in enumerate(as_completed(futures), 1):
        fname, status = fut.result()
        if status == "ok":
            ok += 1
        elif status == "skip":
            skip += 1
        else:
            fail += 1
            print(f"  FAIL {fname}: {status}")
        if i % 10 == 0 or i == len(urls):
            print(f"  {i}/{len(urls)} — ok:{ok} skip:{skip} fail:{fail}")

print(f"\nDone: {ok} downloaded, {skip} skipped, {fail} failed")
