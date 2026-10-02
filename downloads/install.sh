#!/usr/bin/env bash
# MostlyMusic Harvester — one-shot install for Arch Linux
# Usage: bash install.sh
set -e

echo "==> Installing Python deps..."
pip install --quiet textual yt-dlp curl-cffi

echo "==> Checking yt-dlp..."
yt-dlp --version

echo ""
echo "All good! Run:  python downloads/tui.py"
echo ""
echo "Keys inside the TUI:"
echo "  1/2/3/4  switch tabs"
echo "  q        quit"
