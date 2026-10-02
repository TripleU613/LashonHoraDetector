#!/bin/bash
# Download MostlyMusic video files sequentially with curl.
# Usage: ./download_videos.sh [output_dir]
# Default output dir: ./videos/

OUT="${1:-./videos}"
mkdir -p "$OUT"
URLS_FILE="$(dirname "$0")/video_urls.txt"
TOTAL=$(wc -l < "$URLS_FILE")
N=0

while IFS= read -r URL; do
    [ -z "$URL" ] && continue
    N=$((N+1))
    FNAME=$(basename "${URL%%\?*}")
    DEST="$OUT/$FNAME"
    if [ -f "$DEST" ] && [ "$(stat -c%s "$DEST" 2>/dev/null || stat -f%z "$DEST" 2>/dev/null)" -gt 10000 ]; then
        continue
    fi
    echo "[$N/$TOTAL] $FNAME"
    curl -sf -L -o "$DEST" "$URL" \
        -H "User-Agent: Mozilla/5.0" \
        --max-time 300 --retry 2 --retry-delay 5
    if [ $? -ne 0 ]; then
        echo "  FAILED: $URL"
        rm -f "$DEST"
    fi
done < "$URLS_FILE"

echo "Done. Files in $OUT/"
