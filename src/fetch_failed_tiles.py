"""
Re-fetch supermarket POIs for tiles that failed during the initial src/fetch_pois.py run.

The initial run hit transient DNS/server errors on the upper half of Brooklyn for the
supermarket category. This script targets ONLY those tiles, uses a different Overpass
mirror with longer back-off intervals, and merges any newly retrieved POIs back into
the existing data/raw/osm_pois.geojson, deduplicating on osm_id.

Failed tiles (rows 2-3 of the 4x4 Brooklyn grid -> tile indices 10-16):

    Tile 10  row=2 col=1  bbox=(40.6450, -73.9950, 40.6925, -73.9400)
    Tile 11  row=2 col=2  bbox=(40.6450, -73.9400, 40.6925, -73.8850)
    Tile 12  row=2 col=3  bbox=(40.6450, -73.8850, 40.6925, -73.8300)
    Tile 13  row=3 col=0  bbox=(40.6925, -74.0500, 40.7400, -73.9950)
    Tile 14  row=3 col=1  bbox=(40.6925, -73.9950, 40.7400, -73.9400)
    Tile 15  row=3 col=2  bbox=(40.6925, -73.9400, 40.7400, -73.8850)
    Tile 16  row=3 col=3  bbox=(40.6925, -73.8850, 40.7400, -73.8300)

Usage (from project root):
    python src/fetch_failed_tiles.py
"""

import json
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OSM_PATH = RAW_DATA_DIR / "osm_pois.geojson"

# Try the Kumi Systems mirror first; fall back to the main Overpass endpoint.
# DNS / NameResolution errors during the initial run point to either main
# endpoint overload or local DNS instability -- having a second mirror in the
# retry chain is the cheapest way to defeat both.
OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

HEADERS = {
    "User-Agent": "urban-building-ml-student-project/1.0 (retry pass)",
    "Accept": "application/json",
}

# Tiles that failed for the supermarket category during the initial run.
# (south, west, north, east) -- same convention as src/fetch_pois.py.
FAILED_TILES = {
    10: (40.6450, -73.9950, 40.6925, -73.9400),
    11: (40.6450, -73.9400, 40.6925, -73.8850),
    12: (40.6450, -73.8850, 40.6925, -73.8300),
    13: (40.6925, -74.0500, 40.7400, -73.9950),
    14: (40.6925, -73.9950, 40.7400, -73.9400),
    15: (40.6925, -73.9400, 40.7400, -73.8850),
    16: (40.6925, -73.8850, 40.7400, -73.8300),
}

# Only re-fetching supermarket. Convenience is documented as dropped.
CATEGORY = "supermarket"
SELECTORS = ('node["shop"="supermarket"]', 'way["shop"="supermarket"]')


def build_query(bbox):
    south, west, north, east = bbox
    selector_lines = [f"  {sel}({south},{west},{north},{east});" for sel in SELECTORS]
    return f"""
[out:json][timeout:90];
(
{chr(10).join(selector_lines)}
);
out center;
"""


def fetch_with_endpoint_rotation(query, retries_per_endpoint=2, base_sleep=15):
    """Try each endpoint up to retries_per_endpoint times before giving up."""
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(1, retries_per_endpoint + 1):
            try:
                print(f"    [{endpoint.split('//')[1].split('/')[0]}] attempt {attempt}/{retries_per_endpoint}")
                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers=HEADERS,
                    timeout=120,
                )
                if response.status_code == 200:
                    return response.json()
                print(f"    HTTP {response.status_code}: {response.text[:200]}")
            except Exception as exc:
                print(f"    Error: {exc}")

            # Exponential-ish back-off so we are polite to the public endpoint.
            sleep_for = base_sleep * attempt
            print(f"    Sleeping {sleep_for}s before next attempt...")
            time.sleep(sleep_for)

    return None


def element_to_feature(element, category):
    tags = element.get("tags", {})

    if element["type"] == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None

    osm_id = f'{element["type"]}/{element["id"]}'

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "properties": {
            "osm_id": osm_id,
            "category": category,
            "name": tags.get("name"),
            "amenity": tags.get("amenity"),
            "shop": tags.get("shop"),
            "leisure": tags.get("leisure"),
        },
    }


def main():
    assert OSM_PATH.exists(), f"Existing POI file missing: {OSM_PATH}"

    with open(OSM_PATH, "r", encoding="utf-8") as f:
        geo = json.load(f)

    existing_features = geo["features"]
    existing_keys = {
        (feat["properties"]["osm_id"], feat["properties"]["category"])
        for feat in existing_features
    }
    print(f"Loaded existing POI file: {len(existing_features):,} features")

    new_features = []
    summary = {}

    for tile_idx, bbox in FAILED_TILES.items():
        print(f"\nTile {tile_idx} bbox={bbox}")
        query = build_query(bbox)
        data = fetch_with_endpoint_rotation(query)

        if data is None:
            print(f"  Tile {tile_idx}: ALL ENDPOINTS FAILED -- leaving as gap")
            summary[tile_idx] = "FAILED"
            continue

        elements = data.get("elements", [])
        added_here = 0
        for element in elements:
            feature = element_to_feature(element, CATEGORY)
            if feature is None:
                continue
            key = (feature["properties"]["osm_id"], CATEGORY)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            new_features.append(feature)
            added_here += 1

        print(f"  Tile {tile_idx}: retrieved {len(elements)} elements, "
              f"{added_here} new (after dedup)")
        summary[tile_idx] = added_here

        # Polite delay between successful tiles
        time.sleep(8)

    if not new_features:
        print("\nNo new POIs were retrieved. The existing file is unchanged.")
        return

    combined = existing_features + new_features
    geo_out = {
        "type": "FeatureCollection",
        "features": combined,
    }

    with open(OSM_PATH, "w", encoding="utf-8") as f:
        json.dump(geo_out, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("Re-fetch summary")
    print("=" * 60)
    for tile_idx, result in summary.items():
        print(f"  Tile {tile_idx}: {result}")
    print(f"\nTotal new supermarket POIs added: {len(new_features)}")
    print(f"Total features in file: {len(combined):,}")
    print(f"Saved to: {OSM_PATH}")


if __name__ == "__main__":
    main()
