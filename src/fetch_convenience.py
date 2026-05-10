"""
Re-fetch the convenience category for all 16 Brooklyn tiles.

The initial `src/fetch_pois.py` run could not retrieve any convenience stores
because the main Overpass endpoint (`overpass-api.de`) was returning DNS /
NameResolution errors for that category. The supermarket rescue in
`src/fetch_failed_tiles.py` proved that the Kumi Systems mirror is healthy,
so we re-run the entire convenience pass against it.

Strategy is identical to `fetch_failed_tiles.py`:
- Kumi Systems first, main Overpass endpoint as fallback.
- Exponential-ish back-off between attempts.
- Dedup against the existing GeoJSON on `(osm_id, category)`.
- Merge results in-place into `data/raw/osm_pois.geojson`.

Usage (from project root):
    python src/fetch_convenience.py
"""

import json
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OSM_PATH = RAW_DATA_DIR / "osm_pois.geojson"

OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

HEADERS = {
    "User-Agent": "urban-building-ml-student-project/1.0 (convenience rescue)",
    "Accept": "application/json",
}

# Brooklyn 4x4 tile grid -- identical to fetch_pois.py / fetch_failed_tiles.py.
BROOKLYN_BBOX = (40.55, -74.05, 40.74, -73.83)

CATEGORY = "convenience"
SELECTORS = ('node["shop"="convenience"]', 'way["shop"="convenience"]')


def make_tiles(bbox, rows=4, cols=4):
    south, west, north, east = bbox
    lat_step = (north - south) / rows
    lon_step = (east - west) / cols
    tiles = {}
    for i in range(rows):
        for j in range(cols):
            idx = i * cols + j + 1
            tiles[idx] = (
                south + i * lat_step,
                west + j * lon_step,
                south + (i + 1) * lat_step,
                west + (j + 1) * lon_step,
            )
    return tiles


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
    for endpoint in OVERPASS_ENDPOINTS:
        host = endpoint.split("//")[1].split("/")[0]
        for attempt in range(1, retries_per_endpoint + 1):
            try:
                print(f"    [{host}] attempt {attempt}/{retries_per_endpoint}")
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

    tiles = make_tiles(BROOKLYN_BBOX, rows=4, cols=4)
    new_features = []
    summary = {}

    for tile_idx, bbox in tiles.items():
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
    print("Convenience rescue summary")
    print("=" * 60)
    for tile_idx, result in summary.items():
        print(f"  Tile {tile_idx:>2}: {result}")
    print(f"\nTotal new convenience POIs added: {len(new_features)}")
    print(f"Total features in file: {len(combined):,}")
    print(f"Saved to: {OSM_PATH}")


if __name__ == "__main__":
    main()
