#!/usr/bin/env python3
"""
Download videos from MostlyMusic's Vimeo account using the exposed API token.
Token found in: https://mostlymusic.com/cdn/shop/t/139/assets/test.js

Usage: python3 vimeo_download.py [output_dir]
Requires: yt-dlp (pip install yt-dlp)
"""
import urllib.request, json, time, os, subprocess, re
from pathlib import Path

TOKEN = "bf04e67ba612bc5df1e342fcdb4b117f"
USER_ID = "30452144"
ALBUM_ID = "7669939"

# Skip obvious wedding/non-music content
SKIP_WORDS = {
    'first dance', 'zaftig', 'chuppah', 'chosson', 'kallah',
    'bar mitzvah', 'bat mitzvah', 'wedding', 'vort', 'l\'chaim',
    'lchaim', 'torah class', 'shiur', 'dvar torah', 'parsha'
}

def api_get(endpoint, retries=8):
    url = f"https://api.vimeo.com{endpoint}"
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={'Authorization': f'bearer {TOKEN}'})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 70 * (2 ** attempt)
                print(f"Rate limited (attempt {attempt+1}), waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                return None
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
    return None

def get_all_videos():
    """Get all video IDs and embed URLs from the album."""
    videos = []
    page = 1
    while True:
        endpoint = (f"/users/{USER_ID}/albums/{ALBUM_ID}/videos"
                   f"?page={page}&per_page=25"
                   f"&fields=uri,name,player_embed_url,duration,privacy")
        data = api_get(endpoint)
        if not data or not data.get('data'):
            break
        for v in data['data']:
            vid_id = v['uri'].split('/')[-1]
            name = v.get('name', '')
            embed_url = v.get('player_embed_url', '')
            skip = any(w in name.lower() for w in SKIP_WORDS)
            videos.append({
                'id': vid_id,
                'name': name,
                'embed_url': embed_url,
                'duration': v.get('duration', 0),
                'skip': skip
            })
        print(f"Page {page}: got {len(data['data'])} videos, total {len(videos)}", flush=True)
        if not data.get('paging', {}).get('next'):
            break
        page += 1
        time.sleep(1.2)  # ~50 req/min - safe
    return videos

def safe_filename(name):
    return re.sub(r'[^\w\s.-]', '_', name)[:80].strip()

def download_video(v, out_dir):
    embed_url = v.get('embed_url', '')
    if not embed_url:
        print(f"  NO EMBED URL: {v['name']}")
        return False
    
    name_safe = safe_filename(v['name'])
    out_path = out_dir / f"{name_safe}.%(ext)s"
    
    cmd = [
        'yt-dlp',
        '--no-warnings',
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '-o', str(out_path),
        '--add-header', 'Referer:https://mostlymusic.com/',
        '--retries', '3',
        embed_url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode == 0:
        print(f"  OK: {v['name']}")
        return True
    else:
        print(f"  FAIL: {result.stderr[-300:]}")
        return False

def main():
    import sys
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('./videos')
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Cache video list
    cache = Path('vimeo_videos.json')
    if cache.exists():
        with open(cache) as f:
            videos = json.load(f)
        print(f"Loaded {len(videos)} videos from cache")
    else:
        print("Fetching video list from Vimeo API...")
        videos = get_all_videos()
        with open(cache, 'w') as f:
            json.dump(videos, f, indent=2)
        print(f"Saved {len(videos)} videos to cache")
    
    eligible = [v for v in videos if not v.get('skip')]
    print(f"\nEligible videos: {len(eligible)} / {len(videos)}")
    
    ok, fail, skip_count = 0, 0, 0
    for v in eligible:
        print(f"\n[{ok+fail+1}/{len(eligible)}] {v['name'][:60]}")
        if download_video(v, out_dir):
            ok += 1
        else:
            fail += 1
        time.sleep(0.5)
    
    print(f"\nDone: {ok} downloaded, {fail} failed, {len(videos)-len(eligible)} skipped (wedding/Torah)")

if __name__ == '__main__':
    main()
