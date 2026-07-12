"""Download a few openly-licensed test images from Wikimedia Commons.

For each class we query the Commons search API, then download the first result
that is a valid raster photo. Files are saved into test_data/ with class-named
filenames so test_folder.py can infer the ground-truth label.

Note: these are real medical/wound images from Wikimedia Commons (openly licensed).
Some are graphic by nature. This is for testing the classifier only.

Usage:
    python fetch_test_images.py
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import time
import urllib.parse

from PIL import Image

OUT_DIR = "test_data"
API = "https://commons.wikimedia.org/w/api.php"
# A descriptive User-Agent is required by the Wikimedia API, else it returns 403.
UA = "InjuryClassifierTest/1.0 (educational ML test; contact: local user)"

# One search term (with fallbacks) per class -> output filename.
CLASSES = [
    ("abrasion_web", ["skin abrasion injury", "graze abrasion skin", "road rash abrasion"]),
    ("bruise_web", ["bruise skin", "hematoma bruise skin", "contusion bruise"]),
    ("burn_web", ["skin burn injury", "second degree burn skin", "thermal burn wound"]),
    ("cut_web", ["cut wound skin", "incised wound finger", "knife cut wound"]),
    ("laceration_web", ["laceration wound", "skin laceration", "lacerated wound"]),
    ("normal_web", ["human forearm skin", "healthy human skin arm", "human skin close up"]),
    ("pressure_wound_web", ["pressure ulcer", "decubitus ulcer", "bedsore pressure ulcer"]),
    ("stab_wound_web", ["stab wound", "stab wound skin", "puncture stab wound"]),
    ("surgical_wound_web", ["surgical wound", "sutured wound", "surgical incision skin",
                             "post operative wound", "surgical stitches wound", "surgical scar"]),
    ("venous_wound_web", ["venous leg ulcer", "venous ulcer wound", "venous stasis ulcer"]),
]


def _get(url: str) -> bytes:
    """Fetch bytes via curl (its CA bundle avoids this Python's SSL cert issues)."""
    proc = subprocess.run(
        ["curl", "-sL", "--max-time", "30", "-A", UA, url],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed ({proc.returncode}) for {url}")
    return proc.stdout


def search_image_urls(term: str, limit: int = 8) -> list[str]:
    """Return candidate direct image (thumb) URLs for a search term."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": term,
        "gsrnamespace": "6",     # File: namespace
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": "640",     # request a 640px-wide thumbnail
    }
    url = API + "?" + urllib.parse.urlencode(params)
    data = json.loads(_get(url).decode("utf-8"))
    pages = data.get("query", {}).get("pages", {})
    urls = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if mime in ("image/jpeg", "image/png"):
            urls.append(info.get("thumburl") or info.get("url"))
    return [u for u in urls if u]


def download_valid_image(term_list: list[str]) -> bytes | None:
    for term in term_list:
        try:
            for url in search_image_urls(term):
                try:
                    raw = _get(url)
                    time.sleep(0.7)  # be gentle: avoid Wikimedia rate-limiting
                    img = Image.open(io.BytesIO(raw))
                    img.verify()  # ensure it's a real, non-corrupt image
                    if min(Image.open(io.BytesIO(raw)).size) >= 100:
                        return raw
                except Exception:
                    continue
        except Exception:
            continue
    return None


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    ok, fail = 0, []
    for name, terms in CLASSES:
        path = os.path.join(OUT_DIR, name + ".jpg")
        if os.path.exists(path):
            print(f"  [skip] {name}: already present")
            ok += 1
            continue
        raw = download_valid_image(terms)
        if raw is None:
            fail.append(name)
            print(f"  [MISS] {name}: no suitable image found")
            continue
        # Save as .jpg (convert to RGB to normalize PNG/CMYK etc.).
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.save(path, "JPEG", quality=90)
        ok += 1
        print(f"  [OK]   {name}: saved {img.size} -> {path}")

    print(f"\nDownloaded {ok}/{len(CLASSES)} images into '{OUT_DIR}'.")
    if fail:
        print(f"Missing: {', '.join(fail)} (re-run to retry, or add manually).")


if __name__ == "__main__":
    main()
