"""Capture the README screenshots and demo video from the running app.

Dev-only: needs `pip install playwright` and a Chromium-based browser (uses the
installed Microsoft Edge, so no browser download). Start the API (port 8000) and the
Vite dev server (port 5173) first. The video is converted to a GIF with ffmpeg
(`playwright install ffmpeg` is also needed for the recording itself):

    python scripts/capture_assets.py
    ffmpeg -i docs/assets/demo.webm -vf "fps=10,scale=960:-1:flags=lanczos,split[a][b];\\
[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=5" docs/assets/demo.gif
"""

import shutil
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:5173"
ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"


def run_strategy(page: Page, pair: str | None = None) -> None:
    if pair:
        page.get_by_role("button", name=pair, exact=True).click()
    page.get_by_role("button", name="Build & backtest").click()
    page.get_by_text("Out-of-sample:").wait_for(timeout=120_000)
    page.wait_for_timeout(800)  # let the charts paint


def screenshots(browser) -> None:
    page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=2)
    page.goto(URL)
    page.wait_for_load_state("networkidle")
    run_strategy(page)
    page.screenshot(path=ASSETS / "overview.png")
    for tab in ("Chart", "Rules", "Code"):
        page.get_by_role("tab", name=tab).click()
        page.wait_for_timeout(700)
        page.screenshot(path=ASSETS / f"{tab.lower()}.png")
    page.close()


def video(browser) -> None:
    tmp = ASSETS / "_video"
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, record_video_dir=tmp, record_video_size={"width": 1280, "height": 800}
    )
    page = context.new_page()
    page.goto(URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)
    run_strategy(page, pair="Gold")
    page.wait_for_timeout(2500)
    for tab in ("Chart", "Rules", "Code"):
        page.get_by_role("tab", name=tab).click()
        page.wait_for_timeout(2200)
    recorded = Path(page.video.path())
    context.close()
    shutil.move(recorded, ASSETS / "demo.webm")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        screenshots(browser)
        if "--no-video" not in sys.argv:
            video(browser)
        browser.close()
    print(f"assets written to {ASSETS}")
