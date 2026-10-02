#!/usr/bin/env python3
"""
Download videos from MostlyMusic's Vimeo account.

Sources:
  1. Vimeo album 7669939 (1162 videos) - requires Vimeo API token
  2. Vimeo IDs embedded directly on product pages (64 found)

IMPORTANT: Run this from a residential IP (NOT a VPS/cloud server).
Vimeo blocks datacenter IPs. Your home internet connection will work fine.

Requirements:
  pip install yt-dlp curl_cffi

Usage:
  python3 vimeo_download.py [output_dir]
  python3 vimeo_download.py ./videos
"""
import urllib.request, json, time, subprocess, re, sys
from pathlib import Path

# ─── credentials ────────────────────────────────────────────────────────────
TOKEN     = "bf04e67ba612bc5df1e342fcdb4b117f"  # from mostlymusic.com/cdn/shop/t/139/assets/test.js
USER_ID   = "30452144"
ALBUM_ID  = "7669939"
REFERER   = "https://mostlymusic.com/"

# ─── content filters ─────────────────────────────────────────────────────────
SKIP_WORDS = {
    'wedding', 'chuppah', 'chosson', 'kallah', 'vort', 'aufruf',
    'bar mitzvah', 'bat mitzvah', 'first dance',
    'shiur', 'dvar torah', 'parsha', 'torah class', 'lecture',
    'borchi nafshi', 'perek shira', 'chofetz chaim', 'living torah',
}

# ─── pre-crawled product-page embed IDs ──────────────────────────────────────
# These were extracted by crawling all 412 video product pages without Shopify CDN URLs.
# Key: some videos are embeddable even if the album API token can't access them individually.
PRODUCT_EMBED_IDS = [
    ("1042036950", "The Ladies Of Loganberry Lane - Season 1 Ep2"),
    ("1019515112", "Kumzing 3"),
    ("831260771",  "Michoel Schnitzler - Di Neshuma Flam"),
    ("784392282",  "Talent Unite - Thankful"),
    ("782630955",  "Scandal"),
    ("755301431",  "Zusman 2.0"),
    ("757663782",  "Malkie Knopfler - The Malkie Show"),
    ("701347214",  "Boruch Perlowitz - 2 Desperate"),
    ("718419949",  "The Lost Treasure"),
    ("693301399",  "Limelight Musical - Fraulein"),
    ("601311069",  "Boruch Perlowitz - Desperate Measures"),
    ("495280446",  "Yaakov Shwekey - Live Park"),
    ("527594277",  "Regal Production - Anne of the Green Gables"),
    ("492148372",  "Framed"),
    ("473085462",  "Jewish Tales of the Unexpected - The Permeable Man"),
    ("411142838",  "Miami Experience 4 - Shiru Lo 1994"),
    ("381672107",  "Boruch Perlowitz - The Skull Of A Genius"),
    ("402733616",  "Malky We Will Carry On Your Legacy"),
    ("269669613",  "The Twins From France - On The Roof"),
    ("246632532",  "The Twins From France - Back to China"),
    ("303075310",  "Uncle Moishy's World"),
    ("282859960",  "The War Against Bullying"),
    ("220681039",  "Interen Shpiel"),
    ("212494641",  "DreamCatch Studios - Trust Me"),
    ("261886178",  "A Lebedigeh Tzavueh"),
    ("276067793",  "Mechel"),
    ("195675662",  "Interen Riken"),
    ("192513862",  "JM Video Collection 3"),
    ("191867967",  "Mendy Music - Kosher Fitness Workout"),
    ("114990175",  "Interen Bild"),
    ("107605260",  "Uncle Moishy - The Very Best of"),
    ("104058375",  "Robin Garbose - The Heart That Sings"),
    ("104058389",  "Uncle Moishy DVD Volume 9"),
    ("104058388",  "Uncle Moishy Volume 8"),
    ("104058387",  "Uncle Moishy Volume 7"),
    ("104058381",  "Uncle Moishy DVD Volume 2"),
    ("104058383",  "Uncle Moishy Volume 4"),
    ("104058380",  "Uncle Moishy DVD Volume 1"),
]


def api_get(endpoint, retries=8):
    url = f"https://api.vimeo.com{endpoint}"
    for attempt in range(retries):
        req = urllib.request.Request(
            url, headers={'Authorization': f'bearer {TOKEN}',
                          'Accept': 'application/vnd.vimeo.*+json;version=3.4'})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(70 * (2 ** attempt), 600)
                print(f"  Rate limited (attempt {attempt+1}/{retries}), waiting {wait}s...", flush=True)
                time.sleep(wait)
            elif e.code in (401, 403, 404):
                return None
            else:
                time.sleep(10)
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(10)
    return None


def get_album_videos():
    """Fetch all videos from the Vimeo album using the API. Rate limited at 50/min."""
    cache = Path('vimeo_album_cache.json')
    if cache.exists():
        data = json.loads(cache.read_text())
        print(f"Loaded {len(data)} album videos from cache")
        return data

    print("Fetching album videos from Vimeo API (rate limited, ~50/min)...")
    videos = []
    page = 1
    while True:
        ep = (f"/users/{USER_ID}/albums/{ALBUM_ID}/videos"
              f"?page={page}&per_page=25"
              f"&fields=uri,name,player_embed_url,duration")
        data = api_get(ep)
        if not data or not data.get('data'):
            print(f"  No data on page {page}, stopping.")
            break
        for v in data['data']:
            vid_id = v['uri'].split('/')[-1]
            skip = any(w in v.get('name', '').lower() for w in SKIP_WORDS)
            videos.append({
                'id': vid_id, 'name': v.get('name', ''),
                'embed_url': v.get('player_embed_url', ''),
                'duration': v.get('duration', 0), 'skip': skip,
                'source': 'album_api'
            })
        print(f"  Page {page}: {len(data['data'])} videos, total={len(videos)}", flush=True)
        if not data.get('paging', {}).get('next'):
            break
        page += 1
        time.sleep(1.5)

    cache.write_text(json.dumps(videos, indent=2))
    return videos


def download_video(vid_id, name, embed_url, out_dir):
    safe = re.sub(r'[^\w\s.-]', '_', name)[:80].strip() or vid_id
    dest = out_dir / safe

    # Check if already downloaded
    for ext in ('mp4', 'mkv', 'webm', 'mov'):
        if (out_dir / f"{safe}.{ext}").exists():
            return 'skip'

    # Build yt-dlp command - try embed URL first, fall back to direct ID
    urls_to_try = []
    if embed_url:
        urls_to_try.append(embed_url)
    urls_to_try.append(f"https://vimeo.com/{vid_id}")

    for url in urls_to_try:
        cmd = [
            'yt-dlp',
            '--no-warnings',
            '--impersonate', 'chrome',          # bypass Cloudflare TLS fingerprinting
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '-o', str(dest) + '.%(ext)s',
            '--add-header', f'Referer:{REFERER}',
            '--retries', '3',
            '--fragment-retries', '5',
            url
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                return 'ok'
        except subprocess.TimeoutExpired:
            return 'timeout'

    err = result.stderr[-400:] if 'result' in dir() else 'unknown error'
    return f'fail:{err}'


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('./vimeo_videos')
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("MostlyMusic Vimeo Downloader")
    print("Run from residential IP only (Vimeo blocks datacenters)")
    print("=" * 60)

    # Check yt-dlp and curl-cffi
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: yt-dlp not found. Run: pip install yt-dlp")
        sys.exit(1)
    try:
        import curl_cffi
    except ImportError:
        print("WARNING: curl_cffi not installed. yt-dlp may fail on Vimeo.")
        print("  Fix: pip install curl-cffi")

    # Source 1: Album API
    print("\n[1] Fetching album videos from Vimeo API...")
    album_videos = get_album_videos()
    eligible_album = [v for v in album_videos if not v['skip']]
    print(f"Album: {len(eligible_album)} eligible / {len(album_videos)} total")

    # Source 2: Pre-crawled product page embeds
    print("\n[2] Loading pre-crawled product page embed IDs...")
    embed_videos = [
        {'id': vid_id, 'name': name, 'embed_url': '',
         'source': 'product_embed', 'skip': False}
        for vid_id, name in PRODUCT_EMBED_IDS
    ]
    print(f"Product embeds: {len(embed_videos)} videos")

    # Combine, deduplicate by ID
    seen_ids = set()
    all_videos = []
    for v in eligible_album + embed_videos:
        if v['id'] not in seen_ids:
            seen_ids.add(v['id'])
            all_videos.append(v)

    print(f"\nTotal unique eligible videos: {len(all_videos)}")
    print(f"Output directory: {out_dir.resolve()}")
    print("\nStarting downloads...\n")

    ok = fail = skip_count = 0
    for i, v in enumerate(all_videos, 1):
        src = v.get('source', '')
        print(f"[{i}/{len(all_videos)}] ({src}) {v['name'][:55]}")
        status = download_video(v['id'], v['name'], v.get('embed_url', ''), out_dir)
        if status == 'ok':
            ok += 1
            print(f"  OK")
        elif status == 'skip':
            skip_count += 1
        else:
            fail += 1
            if 'fail:' in str(status):
                print(f"  FAIL: {status[5:200]}")
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Done: {ok} downloaded, {skip_count} already existed, {fail} failed")


if __name__ == '__main__':
    main()
