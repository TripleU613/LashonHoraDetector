#!/usr/bin/env python3
"""
MostlyMusic Harvester — interactive TUI
Run: python tui.py
Deps: pip install textual yt-dlp curl-cffi
"""

import asyncio, json, os, re, ssl, subprocess, sys, time, urllib.request
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
    from textual.reactive import reactive
    from textual.screen import Screen
    from textual.widgets import (
        Button, DataTable, Footer, Header, Label, Log,
        ProgressBar, Rule, Static, TabbedContent, TabPane,
    )
    from textual import work
    from rich.text import Text
except ImportError:
    print("Missing deps. Run:  pip install textual yt-dlp curl-cffi")
    sys.exit(1)

# ── paths ─────────────────────────────────────────────────────────────────────
HERE        = Path(__file__).parent
CDN_URLS    = HERE / "video_urls.txt"
VIMEO_PY    = HERE / "vimeo_download.py"
SSL_CTX     = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt") if Path("/root/.ccr/ca-bundle.crt").exists() else ssl.create_default_context()

# ── counts ────────────────────────────────────────────────────────────────────
CDN_COUNT   = len([l for l in CDN_URLS.read_text().splitlines() if l.strip()]) if CDN_URLS.exists() else 0
VIMEO_EMBED = 99   # hardcoded from crawl
VIMEO_ALBUM = 1162

BANNER = r"""
  __  __           _   _        __  __           _
 |  \/  | ___  ___| |_| |_   _ |  \/  |_   _ ___(_) ___
 | |\/| |/ _ \/ __| __| | | | || |\/| | | | / __| |/ __|
 | |  | | (_) \__ \ |_| | |_| || |  | | |_| \__ \ | (__
 |_|  |_|\___/|___/\__|_|\__, ||_|  |_|\__,_|___/_|\___|
                          |___/   H A R V E S T E R
"""

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
Screen {
    background: #0d0d1a;
    color: #e8e8f0;
}

#banner {
    color: #7c6af7;
    text-align: center;
    padding: 0 2;
}

#stats-bar {
    height: 3;
    background: #141428;
    border: solid #7c6af7;
    padding: 0 3;
    content-align: center middle;
}

.stat-item {
    color: #a8f0c8;
    padding: 0 4;
}

TabbedContent {
    height: 1fr;
}

TabPane {
    padding: 1 2;
}

.panel-title {
    color: #f7c96a;
    text-style: bold;
    padding-bottom: 1;
}

.action-btn {
    margin: 1 2;
    min-width: 24;
    background: #1e1e3a;
    border: solid #7c6af7;
    color: #e8e8f0;
}

.action-btn:hover {
    background: #7c6af7;
    color: #ffffff;
}

.action-btn.danger {
    border: solid #f77c7c;
    color: #f77c7c;
}

.action-btn.danger:hover {
    background: #f77c7c;
    color: #ffffff;
}

.action-btn.success {
    border: solid #a8f0c8;
    color: #a8f0c8;
}

.action-btn.success:hover {
    background: #a8f0c8;
    color: #0d0d1a;
}

ProgressBar {
    margin: 0 0 1 0;
}

ProgressBar > .bar--bar {
    color: #7c6af7;
}

ProgressBar > .bar--complete {
    color: #a8f0c8;
}

Log {
    background: #0a0a18;
    border: solid #2a2a4a;
    scrollbar-color: #7c6af7;
}

DataTable {
    background: #0a0a18;
    border: solid #2a2a4a;
}

DataTable > .datatable--header {
    background: #141428;
    color: #7c6af7;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #2a2a4a;
    color: #e8e8f0;
}

.warn-box {
    background: #2a1a0a;
    border: solid #f7c96a;
    padding: 1 2;
    margin-bottom: 1;
    color: #f7c96a;
}

.info-box {
    background: #0a1a2a;
    border: solid #7c6af7;
    padding: 1 2;
    margin-bottom: 1;
}

#footer-status {
    height: 1;
    background: #141428;
    color: #a8a8c8;
    padding: 0 2;
}

.progress-label {
    color: #a8a8c8;
    margin-bottom: 0;
}

.counter {
    color: #a8f0c8;
    text-style: bold;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
class CdnPane(TabPane):
    """Download the 179 direct Shopify CDN video previews."""

    def compose(self) -> ComposeResult:
        yield Label("■ Shopify CDN Preview Videos", classes="panel-title")
        yield Static(
            f"[dim]179 publicly accessible MP4s from mostlymusic.com/cdn/shop/videos/[/]\n"
            f"No auth needed — downloads from any IP.",
            classes="info-box",
        )
        yield Horizontal(
            Button("▶  Download All (179)", id="btn-cdn-start", classes="action-btn success"),
            Button("⏹  Stop", id="btn-cdn-stop", classes="action-btn danger"),
            Button("📂  Open folder", id="btn-cdn-open", classes="action-btn"),
        )
        yield Label("", id="cdn-progress-label", classes="progress-label")
        yield ProgressBar(total=CDN_COUNT, id="cdn-progress", show_eta=True)
        yield Log(id="cdn-log", max_lines=300, markup=True)

    _running = reactive(False)
    _stop    = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-cdn-start" and not self._running:
            self._stop = False
            self.download_cdn()
        elif bid == "btn-cdn-stop":
            self._stop = True
        elif bid == "btn-cdn-open":
            out = HERE / "videos"
            out.mkdir(exist_ok=True)
            subprocess.Popen(["xdg-open", str(out)])

    @work(thread=True)
    def download_cdn(self) -> None:
        self._running = True
        log  = self.query_one("#cdn-log", Log)
        prog = self.query_one("#cdn-progress", ProgressBar)
        lbl  = self.query_one("#cdn-progress-label", Label)
        out  = HERE / "videos"
        out.mkdir(exist_ok=True)

        urls = [u.strip() for u in CDN_URLS.read_text().splitlines() if u.strip()]
        ok = skip = fail = 0
        prog.update(progress=0, total=len(urls))

        for i, url in enumerate(urls, 1):
            if self._stop:
                log.write_line("[yellow]■ Stopped by user[/]")
                break

            fname = url.split("?")[0].split("/")[-1]
            dest  = out / fname
            lbl.update(f"[{i}/{len(urls)}]  {fname[:55]}")

            if dest.exists() and dest.stat().st_size > 10_000:
                skip += 1
                prog.advance(1)
                continue

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, context=SSL_CTX, timeout=120) as resp, \
                     open(dest, "wb") as f:
                    while chunk := resp.read(65536):
                        f.write(chunk)
                ok += 1
                log.write_line(f"[green]✓[/] {fname}")
            except Exception as e:
                fail += 1
                dest.unlink(missing_ok=True)
                log.write_line(f"[red]✗[/] {fname}: {e}")
            prog.advance(1)

        lbl.update(f"Done — {ok} downloaded, {skip} skipped, {fail} failed")
        log.write_line(f"\n[bold green]✓ Complete: {ok} new, {skip} already had, {fail} errors[/]")
        self._running = False


# ─────────────────────────────────────────────────────────────────────────────
class VimeoPane(TabPane):
    """Stream/download Vimeo content via yt-dlp."""

    def compose(self) -> ComposeResult:
        yield Label("■ Vimeo Content — 1,000+ Videos", classes="panel-title")
        yield Static(
            "⚠  Must run from a RESIDENTIAL IP.\n"
            "    Vimeo blocks cloud/datacenter IPs at the network level.\n"
            "    Run this tool from your home connection.",
            classes="warn-box",
        )
        yield Static(
            f"[bold]Sources[/]\n"
            f"  • Vimeo album 7669939 — [green]{VIMEO_ALBUM}[/] videos (fetched via API)\n"
            f"  • Product-page embeds  — [green]{VIMEO_EMBED}[/] pre-crawled IDs\n"
            f"  • Content filter applied: skips weddings, Torah lectures\n\n"
            f"[dim]API token: bf04e67ba612bc5df1e342fcdb4b117f (from site JS)[/]",
            classes="info-box",
        )
        yield Horizontal(
            Button("▶  Start Vimeo Downloads", id="btn-vimeo-start", classes="action-btn success"),
            Button("⏹  Stop", id="btn-vimeo-stop", classes="action-btn danger"),
            Button("📂  Open folder", id="btn-vimeo-open", classes="action-btn"),
        )
        yield Label("Checking yt-dlp…", id="vimeo-status", classes="progress-label")
        yield ProgressBar(total=VIMEO_ALBUM + VIMEO_EMBED, id="vimeo-progress", show_eta=True)
        yield Log(id="vimeo-log", max_lines=500, markup=True)

    _running = reactive(False)
    _stop    = False
    _proc    = None

    def on_mount(self) -> None:
        self.check_deps()

    @work(thread=True)
    def check_deps(self) -> None:
        status = self.query_one("#vimeo-status", Label)
        ok = []
        for tool in ("yt-dlp",):
            if subprocess.run(["which", tool], capture_output=True).returncode == 0:
                ok.append(f"[green]✓ {tool}[/]")
            else:
                ok.append(f"[red]✗ {tool} missing — pip install yt-dlp[/]")
        try:
            import curl_cffi  # noqa
            ok.append("[green]✓ curl-cffi[/]")
        except ImportError:
            ok.append("[red]✗ curl-cffi missing — pip install curl-cffi[/]")
        status.update("  ".join(ok))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-vimeo-start" and not self._running:
            self._stop = False
            self.run_vimeo()
        elif bid == "btn-vimeo-stop":
            self._stop = True
            if self._proc:
                self._proc.terminate()
        elif bid == "btn-vimeo-open":
            out = HERE / "vimeo_videos"
            out.mkdir(exist_ok=True)
            subprocess.Popen(["xdg-open", str(out)])

    @work(thread=True)
    def run_vimeo(self) -> None:
        self._running = True
        log    = self.query_one("#vimeo-log", Log)
        status = self.query_one("#vimeo-status", Label)

        log.write_line("[bold]Launching vimeo_download.py …[/]")
        status.update("Running — watch log below")

        out = HERE / "vimeo_videos"
        out.mkdir(exist_ok=True)

        cmd = [sys.executable, str(VIMEO_PY), str(out)]
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in self._proc.stdout:
                line = line.rstrip()
                if self._stop:
                    break
                color = "green" if line.startswith("  OK") else \
                        "red"   if "FAIL" in line          else \
                        "yellow" if "Rate limited" in line  else \
                        "dim"
                log.write_line(f"[{color}]{line}[/]")
            self._proc.wait()
        except Exception as e:
            log.write_line(f"[red]Error: {e}[/]")
        finally:
            status.update("Done" if not self._stop else "Stopped")
            self._running = False


# ─────────────────────────────────────────────────────────────────────────────
class StatsPane(TabPane):
    """What was found — the reconnaissance summary."""

    def compose(self) -> ComposeResult:
        yield Label("■ Reconnaissance Summary", classes="panel-title")

        table = DataTable(id="stats-table", cursor_type="row")
        table.add_columns("Source", "Count", "Auth needed", "How to get it")
        table.add_rows([
            ("Shopify CDN MP4 previews", "179",   "None",      "CDN tab → Download All"),
            ("Vimeo album (API)",         "1,162", "Vimeo API", "Vimeo tab (residential IP)"),
            ("Vimeo product embeds",      "99",    "None",      "Vimeo tab (residential IP)"),
            ("Super Downloads NON-DRM",   "960+",  "Purchase",  "⛔ Blocked — signed S3 URLs"),
            ("Super Downloads DRM",       "~80",   "Purchase",  "⛔ Blocked — Widevine/FairPlay"),
        ])
        yield table

        yield Rule()
        yield Static(
            "[bold yellow]How it works[/]\n\n"
            "[bold]CDN previews[/]  — every product page with a [dim]<video><source>[/] tag has a\n"
            "  public Shopify CDN URL at  cdn/shop/videos/c/vp/…/….HD-1080p-….mp4\n"
            "  No auth, no signing.  179 unique files found across 1 241 products.\n\n"
            "[bold]Vimeo[/]  — MostlyMusic owns Vimeo user [cyan]30452144[/], album [cyan]7669939[/].\n"
            "  API token [cyan]bf04e67ba612bc5df1e342fcdb4b117f[/] found in site JS (test.js).\n"
            "  Videos have  embed:public  so yt-dlp + Referer works from a home IP.\n"
            "  Vimeo blocks ASN ranges for cloud/data-centre providers at network level.\n\n"
            "[bold]Super Downloads (Sky Pilot)[/]  — every other video lives on\n"
            "  mm-uxrv.com (private S3, AccessDenied on listing).\n"
            "  Download URLs are signed S3 pre-signed links generated server-side\n"
            "  only for authenticated sessions that own the order.\n"
            "  All endpoints probed: /apps/downloads/visits/, /pages/player,\n"
            "  Storefront API metafields, app proxy — all blocked without auth.",
            classes="info-box",
        )

        yield Rule()
        yield Static(
            "[bold]Vimeo API token scope[/]  (from crawl)\n"
            "  • /users/30452144/albums/7669939/videos — returns full album list ✓\n"
            "  • Individual video data via /videos/{id}  — accessible ✓\n"
            "  • Download links via /videos/{id}/files   — [red]403 Forbidden[/] (not purchased)\n\n"
            "[bold]Product tag breakdown[/]  (200-product sample)\n"
            "  NON-DRM : 193 / 200   →  plain MP4 behind Super Downloads auth\n"
            "  DRM-PROTECTED :  7 / 200   →  HLS/DASH with Widevine + FairPlay",
            classes="info-box",
        )


# ─────────────────────────────────────────────────────────────────────────────
class HelpPane(TabPane):
    def compose(self) -> ComposeResult:
        yield Label("■ Quick Start", classes="panel-title")
        yield Static(
            "[bold]Install (Arch Linux)[/]\n\n"
            "  [cyan]pip install textual yt-dlp curl-cffi[/]\n"
            "  [dim]# or: pip install --user textual yt-dlp curl-cffi[/]\n\n"
            "[bold]Run[/]\n\n"
            "  [cyan]python tui.py[/]\n\n"
            "[bold]Keys[/]\n\n"
            "  [yellow]Tab / ←→[/]   switch panes\n"
            "  [yellow]q[/]           quit\n"
            "  [yellow]↑↓[/]         scroll log / table\n\n"
            "[bold]Folder layout[/]\n\n"
            "  downloads/videos/         ← 179 CDN MP4s land here\n"
            "  downloads/vimeo_videos/   ← Vimeo downloads land here\n"
            "  downloads/video_urls.txt  ← raw CDN URL list\n"
            "  downloads/vimeo_download.py  ← standalone Vimeo script\n\n"
            "[bold]Run Vimeo downloader standalone[/]\n\n"
            "  [cyan]python vimeo_download.py ./vimeo_videos[/]\n"
            "  [dim]Must be on a residential (home) IP — not a VPS/cloud server.[/]",
            classes="info-box",
        )


# ─────────────────────────────────────────────────────────────────────────────
class MostlyMusicApp(App):
    CSS = CSS
    TITLE = "MostlyMusic Harvester"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("1", "switch_tab('cdn')", "CDN", show=False),
        Binding("2", "switch_tab('vimeo')", "Vimeo", show=False),
        Binding("3", "switch_tab('stats')", "Stats", show=False),
        Binding("4", "switch_tab('help')", "Help", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(BANNER, id="banner")
        yield Horizontal(
            Static(f"📼  [bold]{CDN_COUNT}[/] CDN videos", classes="stat-item"),
            Static(f"🎬  [bold]{VIMEO_ALBUM + VIMEO_EMBED}[/] Vimeo clips", classes="stat-item"),
            Static(f"⛔  [bold]960+[/] behind paywall", classes="stat-item"),
            id="stats-bar",
        )
        with TabbedContent(initial="cdn"):
            yield CdnPane("📼  CDN", id="cdn")
            yield VimeoPane("🎬  Vimeo", id="vimeo")
            yield StatsPane("📊  Stats", id="stats")
            yield HelpPane("❓  Help", id="help")
        yield Footer()

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id


if __name__ == "__main__":
    MostlyMusicApp().run()
