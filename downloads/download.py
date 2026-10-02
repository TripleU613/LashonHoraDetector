#!/usr/bin/env python3
"""
Download all free MostlyMusic MP3s in parallel.
Usage: python3 download.py [output_dir] [--workers N]
"""
import os, sys, re, json
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

def download_file(url, dest, lock, counter, total):
    fname = re.sub(r'\?.*', '', url.split('/')[-1])
    out_path = dest / fname
    if out_path.exists():
        with lock: counter['skip'] += 1
        return True, fname

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        out_path.write_bytes(data)
        with lock:
            counter['ok'] += 1
            done = counter['ok'] + counter['skip'] + counter['fail']
            if done % 50 == 0:
                print(f"  [{done}/{total}] ok={counter['ok']} skip={counter['skip']} fail={counter['fail']}", flush=True)
        return True, fname
    except Exception as e:
        with lock: counter['fail'] += 1
        return False, f"{fname}: {e}"

def main():
    here = Path(__file__).parent
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else here / 'mp3s'
    workers = 10
    for i, arg in enumerate(sys.argv):
        if arg == '--workers' and i+1 < len(sys.argv):
            workers = int(sys.argv[i+1])
    
    out_dir.mkdir(parents=True, exist_ok=True)
    urls = (here / 'urls.txt').read_text().strip().split('\n')
    print(f"Downloading {len(urls)} files to {out_dir} with {workers} workers")
    
    counter = {'ok': 0, 'skip': 0, 'fail': 0}
    lock = Lock()
    
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(download_file, url, out_dir, lock, counter, len(urls)): url for url in urls}
        for f in as_completed(futures):
            pass
    
    print(f"\nDone: {counter['ok']} downloaded, {counter['skip']} skipped, {counter['fail']} failed")

if __name__ == '__main__':
    main()
