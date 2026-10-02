#!/bin/bash
# Download all free MostlyMusic MP3s
# Usage: bash download.sh [output_dir]
# Requirements: curl

OUT="${1:-./mp3s}"
mkdir -p "$OUT"

URLS_FILE="$(dirname "$0")/urls.txt"
TOTAL=$(wc -l < "$URLS_FILE")
COUNT=0
SKIP=0
FAIL=0

while IFS= read -r URL; do
    COUNT=$((COUNT + 1))
    # Extract filename from URL
    FNAME=$(basename "${URL%%\?*}")
    DEST="$OUT/$FNAME"
    
    if [ -f "$DEST" ]; then
        SKIP=$((SKIP + 1))
        continue
    fi
    
    printf "\r[%d/%d] Downloading %s..." "$COUNT" "$TOTAL" "$FNAME"
    
    if curl -sf -L -o "$DEST" "$URL" --max-time 60 --retry 2; then
        : # success
    else
        FAIL=$((FAIL + 1))
        rm -f "$DEST"
    fi
done < "$URLS_FILE"

echo ""
echo "Done: $((COUNT - SKIP - FAIL)) downloaded, $SKIP skipped, $FAIL failed"
