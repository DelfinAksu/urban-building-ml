import json
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_PATH = RAW_DATA_DIR / "osm_pois.geojson"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

HEADERS = {
    "User-Agent": "urban-building-ml-student-project/1.0",
    "Accept": "application/json"
}

# Brooklyn approximate bounding box
# south, west, north, east
BROOKLYN_BBOX = (40.55, -74.05, 40.74, -73.83)

CATEGORIES = {
    "cafe": ('node["amenity"="cafe"]', 'way["amenity"="cafe"]'),
    "restaurant": ('node["amenity"="restaurant"]', 'way["amenity"="restaurant"]'),
    "school": ('node["amenity"="school"]', 'way["amenity"="school"]'),
    "park": ('node["leisure"="park"]', 'way["leisure"="park"]'),
    "supermarket": ('node["shop"="supermarket"]', 'way["shop"="supermarket"]'),
    "convenience": ('node["shop"="convenience"]', 'way["shop"="convenience"]'),
}


def make_tiles(bbox, rows=4, cols=4):
    south, west, north, east = bbox
    lat_step = (north - south) / rows
    lon_step = (east - west) / cols

    tiles = []

    for i in range(rows):
        for j in range(cols):
            tile_south = south + i * lat_step
            tile_north = south + (i + 1) * lat_step
            tile_west = west + j * lon_step
            tile_east = west + (j + 1) * lon_step

            tiles.append((tile_south, tile_west, tile_north, tile_east))

    return tiles


def build_query(category, bbox):
    south, west, north, east = bbox
    selectors = CATEGORIES[category]

    selector_lines = []
    for selector in selectors:
        selector_lines.append(f"  {selector}({south},{west},{north},{east});")

    selector_text = "\n".join(selector_lines)

    query = f"""
[out:json][timeout:60];
(
{selector_text}
);
out center;
"""
    return query


def fetch_overpass(query, retries=3, sleep_seconds=10):
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers=HEADERS,
                timeout=120
            )

            if response.status_code == 200:
                return response.json()

            print(f"HTTP {response.status_code}. Attempt {attempt}/{retries}")
            print(response.text[:300])

        except Exception as e:
            print(f"Error on attempt {attempt}/{retries}: {e}")

        time.sleep(sleep_seconds)

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
            "coordinates": [lon, lat]
        },
        "properties": {
            "osm_id": osm_id,
            "category": category,
            "name": tags.get("name"),
            "amenity": tags.get("amenity"),
            "shop": tags.get("shop"),
            "leisure": tags.get("leisure")
        }
    }


def main():
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    tiles = make_tiles(BROOKLYN_BBOX, rows=4, cols=4)

    features = []
    seen_ids = set()

    for category in CATEGORIES:
        print(f"\nFetching category: {category}")

        for idx, tile in enumerate(tiles, start=1):
            print(f"  Tile {idx}/{len(tiles)}")

            query = build_query(category, tile)
            data = fetch_overpass(query)

            if data is None:
                print("  Failed. Skipping tile.")
                continue

            elements = data.get("elements", [])
            print(f"  Retrieved {len(elements)} elements")

            for element in elements:
                feature = element_to_feature(element, category)

                if feature is None:
                    continue

                unique_key = (feature["properties"]["osm_id"], category)

                if unique_key in seen_ids:
                    continue

                seen_ids.add(unique_key)
                features.append(feature)

            time.sleep(5)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print("\nDone.")
    print(f"Saved {len(features)} POIs to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()