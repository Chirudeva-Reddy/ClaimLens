"""Automated scraper for UAE OEM and replacement vehicle body parts.

Crawls live automotive parts catalogs in the UAE (Al Khateeb UAE / Dubai),
categorizes items into the 21 ClaimLens vehicle components, maps to popular
UAE vehicle brands (Toyota, Nissan, Hyundai, Ford, Lexus, Mercedes-Benz),
and generates empirical price statistics in AED.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OUTPUT_FILE = Path("data/scraped_uae_oem_prices.json")
BASE_URL = "https://alkhateeb.ae/products.json"

BRAND_PATTERNS: dict[str, list[str]] = {
    "Toyota": [
        r"\btoyota\b",
        r"\bland cruiser\b",
        r"\blc300\b",
        r"\blc250\b",
        r"\blc200\b",
        r"\bfj200\b",
        r"\bfj76\b",
        r"\bfj75\b",
        r"\bfj cruiser\b",
        r"\bprado\b",
        r"\bcamry\b",
        r"\bcorolla\b",
        r"\bhilux\b",
        r"\brevo\b",
        r"\bvigo\b",
        r"\byaris\b",
        r"\brav4\b",
        r"\btundra\b",
        r"\bfortuner\b",
        r"\bhiace\b",
    ],
    "Nissan": [
        r"\bnissan\b",
        r"\bpatrol\b",
        r"\bsunny\b",
        r"\baltima\b",
        r"\bx-trail\b",
        r"\bmaxima\b",
        r"\bnavara\b",
        r"\by62\b",
        r"\bsafari\b",
    ],
    "Hyundai": [
        r"\bhyundai\b",
        r"\belantra\b",
        r"\baccent\b",
        r"\bsonata\b",
        r"\btucson\b",
        r"\bsanta fe\b",
        r"\bkia\b",
        r"\bsportage\b",
    ],
    "Ford": [
        r"\bford\b",
        r"\bbronco\b",
        r"\bf-150\b",
        r"\branger\b",
        r"\bexplorer\b",
        r"\bedge\b",
        r"\bexpedition\b",
    ],
    "Lexus": [
        r"\blexus\b",
        r"\blx570\b",
        r"\blx600\b",
        r"\bes350\b",
        r"\brx350\b",
        r"\bis300\b",
    ],
    "Mercedes-Benz": [
        r"\bmercedes\b",
        r"\bbenz\b",
        r"\bg-class\b",
        r"\bg63\b",
        r"\bc-class\b",
        r"\be-class\b",
        r"\bs-class\b",
        r"\bglc\b",
        r"\bgle\b",
    ],
}

PART_PATTERNS: dict[str, list[str]] = {
    "front-bumper": [r"front bumper", r"f\.bumper", r"bumper front", r"front bumper guard"],
    "back-bumper": [r"rear bumper", r"back bumper", r"bumper rear", r"rear bumper guard"],
    "hood": [r"\bhood\b", r"\bbonnet\b", r"engine hood", r"engine cover"],
    "front-door": [r"front door", r"door front"],
    "back-door": [r"rear door", r"back door", r"door rear"],
    "trunk": [r"\btrunk\b", r"\btailgate\b", r"boot lid", r"rear hatch", r"tail gate"],
    "roof": [r"\broof\b", r"roof rack", r"sunroof", r"roof rail"],
    "front-light": [
        r"headlight",
        r"head light",
        r"head lamp",
        r"fog lamp",
        r"fog light",
        r"front lamp",
    ],
    "back-light": [
        r"taillight",
        r"tail light",
        r"tail lamp",
        r"rear light",
        r"brake light",
        r"rear lamp",
    ],
    "left-mirror": [r"side mirror.*left", r"mirror.*left", r"left.*mirror"],
    "right-mirror": [r"side mirror.*right", r"mirror.*right", r"right.*mirror", r"side mirror"],
    "fender": [r"fender", r"fender flare", r"mudguard", r"fender skirt"],
    "quarter-panel": [r"quarter panel", r"rear quarter"],
    "rocker-panel": [r"rocker panel", r"side skirt", r"running board", r"foot step"],
    "front-glass": [r"windshield", r"windscreen", r"front glass"],
    "back-glass": [r"rear glass", r"back glass"],
    "grille": [r"\bgrill\b", r"\bgrille\b", r"front grill", r"radiator grill"],
    "wheel": [r"wheel", r"rim", r"hubcap", r"hub cap", r"alloy wheel"],
}


def create_ssl_context() -> ssl.SSLContext:
    """Creates an SSL context that handles corporate/local proxy certificates."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_page(page: int, ctx: ssl.SSLContext, max_retries: int = 3) -> list[dict[str, Any]]:
    """Fetches a single page of products from the Shopify JSON API."""
    url = f"{BASE_URL}?limit=250&page={page}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload.get("products", [])
        except Exception as err:  # noqa: BLE001
            if attempt == max_retries - 1:
                print(f"Failed to fetch page {page} after {max_retries} attempts: {err}")
                return []
            time.sleep(1.0)
    return []


def classify_product(title: str) -> tuple[str, list[str]]:
    """Identifies the vehicle brand and matching component classes from product title."""
    title_lower = title.lower()

    # Match brand
    matched_brand = "General Market Standard"
    for brand, patterns in BRAND_PATTERNS.items():
        if any(re.search(pat, title_lower) for pat in patterns):
            matched_brand = brand
            break

    # Match components
    matched_parts: list[str] = []
    for part, patterns in PART_PATTERNS.items():
        if any(re.search(pat, title_lower) for pat in patterns):
            matched_parts.append(part)

    return matched_brand, matched_parts


def scrape_all_parts(max_pages: int = 30) -> dict[str, Any]:
    """Crawls all pages and compiles statistical OEM parts pricing in AED."""
    ctx = create_ssl_context()
    raw_matches: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))

    total_scanned = 0
    total_matched_parts = 0
    print(f"Starting crawl of UAE parts catalog ({BASE_URL})...")

    for page in range(1, max_pages + 1):
        products = fetch_page(page, ctx)
        if not products:
            print(f"No more products returned at page {page}. Crawl complete.")
            break

        total_scanned += len(products)
        page_matches = 0

        for p in products:
            title = p.get("title", "").strip()
            handle = p.get("handle", "")
            variants = p.get("variants", [])
            price = float(variants[0]["price"]) if variants and variants[0].get("price") else 0.0

            # Filter out zero or token dummy prices
            if price <= 10.0:
                continue

            brand, matched_parts = classify_product(title)
            if not matched_parts:
                continue

            product_url = f"https://alkhateeb.ae/products/{handle}" if handle else ""
            item_record = {
                "title": title,
                "price_aed": price,
                "url": product_url,
            }

            for part in matched_parts:
                raw_matches[brand][part].append(item_record)
                raw_matches["General Market Standard"][part].append(item_record)
                page_matches += 1

        total_matched_parts += page_matches
        print(f"Page {page:02d}: Scanned {len(products)} products, matched {page_matches} body components.")
        time.sleep(0.15)  # Respectful crawl rate limit

    print(f"\nCompleted crawl: {total_scanned} total products examined, {total_matched_parts} component matches.")

    # Calculate statistics per (Brand, Component)
    brand_stats: dict[str, dict[str, Any]] = {}
    for brand, parts_dict in raw_matches.items():
        brand_stats[brand] = {}
        for part, items in parts_dict.items():
            prices = sorted(item["price_aed"] for item in items)
            n = len(prices)
            if n == 0:
                continue
            median_price = prices[n // 2] if n % 2 != 0 else round((prices[n // 2 - 1] + prices[n // 2]) / 2.0, 2)
            brand_stats[brand][part] = {
                "sample_count": n,
                "min_price_aed": round(prices[0], 2),
                "max_price_aed": round(prices[-1], 2),
                "median_price_aed": round(median_price, 2),
                "examples": items[:5],
            }

    output_payload: dict[str, Any] = {
        "metadata": {
            "source": "Al Khateeb UAE Automotive Collision Parts Catalog (Dubai/UAE)",
            "source_url": "https://alkhateeb.ae/",
            "currency": "AED",
            "scraped_at_utc": datetime.now(UTC).isoformat(),
            "total_products_scanned": total_scanned,
            "total_parts_matched": total_matched_parts,
            "brands_covered": list(brand_stats.keys()),
        },
        "brands": brand_stats,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"Scraped data successfully saved to: {OUTPUT_FILE}")
    return output_payload


if __name__ == "__main__":
    scrape_all_parts()
