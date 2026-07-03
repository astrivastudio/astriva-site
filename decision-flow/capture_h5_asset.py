#!/usr/bin/env python3
"""
Astriva h5 landing-page capture script.

Place this file inside the landing-page folder, next to index.html / landing.html.
It renders the real landing page in Chromium, captures it, and outputs an image
that is EXACTLY the size of the h5 browser interior used by the studio render:

    936 x 916 logical px at SC=4  =>  3744 x 3664 actual px

Install once:
    pip install playwright pillow
    python -m playwright install chromium

Run:
    python capture_h5_asset.py

Outputs:
    assets/h5_landing_fullpage.png   # full local browser capture
    assets/h5_landing_interior.png   # exact 3744x3664 image for the h5 frame
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright

# ===== Studio h5 proof-frame interior =====
SC = 4
PROOF_W_LOGICAL = 936
PROOF_H_LOGICAL = 980
BAR_H_LOGICAL = 64
TARGET_W = PROOF_W_LOGICAL * SC                  # 3744
TARGET_H = (PROOF_H_LOGICAL - BAR_H_LOGICAL) * SC # 3664

# ===== Capture defaults =====
CSS_VIEWPORT_W = 1440
CSS_VIEWPORT_H = 2200
DPR = 3
DEFAULT_ANCHOR = 0.22

REVEAL_CSS = """
*, *::before, *::after {
  animation: none !important;
  transition: none !important;
  scroll-behavior: auto !important;
}
.rv, .file, .cap-item, .proof-stage, .fit-col li, .pr,
.hero-eyebrow, .hero-h1, .hero-lead, .hero-cta-row, .hero-spine {
  opacity: 1 !important;
  transform: none !important;
}
.wipe { clip-path: inset(0 0 0 0) !important; }
.cap-tier2 { max-height: none !important; opacity: 1 !important; }
"""

async def capture_fullpage(html_path: Path, out_path: Path, css_width: int, css_height: int, dpr: float) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": css_width, "height": css_height},
            device_scale_factor=dpr,
        )
        await page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        await page.add_style_tag(content=REVEAL_CSS)
        await page.evaluate("""
            () => {
              document.querySelectorAll('section, .deliv, .proof, .cost, .price, .close, .mech, .fit')
                .forEach(el => el.classList.add('in'));
              window.scrollTo(0, 0);
            }
        """)
        await page.evaluate("document.fonts && document.fonts.ready")
        await page.screenshot(path=str(out_path), full_page=True)
        await browser.close()


def make_interior(fullpage_path: Path, interior_path: Path, anchor: float) -> tuple[int, int, int]:
    src = Image.open(fullpage_path).convert("RGB")
    src_w, src_h = src.size

    # Preserve full desktop width signal: resize to cover WIDTH, then crop vertically.
    scale = TARGET_W / src_w
    resized_h = max(TARGET_H, round(src_h * scale))
    resized = src.resize((TARGET_W, resized_h), Image.LANCZOS)

    max_y = max(0, resized_h - TARGET_H)
    crop_y = round(max_y * anchor)
    crop_y = max(0, min(crop_y, max_y))

    crop = resized.crop((0, crop_y, TARGET_W, crop_y + TARGET_H))
    interior_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(interior_path)
    return src_w, src_h, crop_y


def find_html(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"HTML file not found: {path}")
        return path
    for name in ("index.html", "landing.html", "decision-flow.html"):
        path = Path(name)
        if path.exists():
            return path
    raise FileNotFoundError("No HTML file found. Put this next to index.html or pass --html path/to/file.html")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=None, help="Path to the landing HTML. Defaults to index.html/landing.html.")
    ap.add_argument("--outdir", default="assets", help="Output folder. Default: assets")
    ap.add_argument("--anchor", type=float, default=DEFAULT_ANCHOR, help="Vertical crop anchor 0..1. Default: 0.22")
    ap.add_argument("--width", type=int, default=CSS_VIEWPORT_W, help="CSS viewport width. Default: 1440")
    ap.add_argument("--height", type=int, default=CSS_VIEWPORT_H, help="CSS viewport height. Default: 2200")
    ap.add_argument("--dpr", type=float, default=DPR, help="Device scale factor. Default: 3")
    args = ap.parse_args()

    html = find_html(args.html)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    fullpage = outdir / "h5_landing_fullpage.png"
    interior = outdir / "h5_landing_interior.png"

    print(f"Rendering local page: {html}")
    await capture_fullpage(html, fullpage, args.width, args.height, args.dpr)
    src_w, src_h, crop_y = make_interior(fullpage, interior, args.anchor)

    print("Done.")
    print(f"Full capture: {fullpage}  ({src_w}x{src_h})")
    print(f"H5 interior:  {interior}  ({TARGET_W}x{TARGET_H})")
    print(f"Crop anchor:  {args.anchor}  | crop_y after resize: {crop_y}px")
    print("Now copy assets/h5_landing_interior.png into the studio render folder's assets/ folder.")


if __name__ == "__main__":
    asyncio.run(main())
