"""
Overpass API fetch with:
  - 3 mirror fallbacks
  - Per-mirror retry (up to 3 attempts)
  - MD5-keyed disk cache to avoid redundant downloads
"""

import hashlib
import json
import os
import time

import requests

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache_store")

HIGHWAY_TAGS = {
    "drive": (
        "motorway|trunk|primary|secondary|tertiary|unclassified|"
        "residential|motorway_link|trunk_link|primary_link|"
        "secondary_link|tertiary_link|living_street|road"
    ),
    "walk": (
        "primary|secondary|tertiary|unclassified|residential|"
        "living_street|pedestrian|footway|path|steps|track"
    ),
    "bike": (
        "primary|secondary|tertiary|unclassified|residential|"
        "living_street|cycleway|path|track"
    ),
}

SPEED_KPH = {
    "motorway": 110, "trunk": 90, "primary": 60, "secondary": 50,
    "tertiary": 40, "unclassified": 30, "residential": 30,
    "motorway_link": 60, "trunk_link": 60, "primary_link": 45,
    "secondary_link": 35, "tertiary_link": 25, "living_street": 10,
    "road": 30, "cycleway": 20, "footway": 5, "path": 5,
    "steps": 2, "track": 20, "pedestrian": 5,
}


def _cache_file(bbox, net):
    key = "".join(f"{x:.5f}" for x in bbox) + net
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{h}.json")


def fetch_osm(north, south, east, west, net="drive", log=print):
    cf = _cache_file((north, south, east, west), net)
    if os.path.exists(cf):
        log("✓ Loaded from disk cache")
        with open(cf) as f:
            return json.load(f)

    tags = HIGHWAY_TAGS[net]
    query = (
        f"[out:json][timeout:55];"
        f"(way[\"highway\"~\"^({tags})$\"]"
        f"({south:.6f},{west:.6f},{north:.6f},{east:.6f});>;);"
        f"out body;"
    )

    for mirror in MIRRORS:
        for attempt in range(1, 4):
            try:
                log(f"↓ {mirror.split('/')[2]}  attempt {attempt}/3 …")
                t0 = time.time()
                resp = requests.post(
                    mirror,
                    data={"data": query},
                    timeout=70,
                    headers={"User-Agent": "AStarRouteFinder/3.0"},
                )
                if resp.status_code in (502, 503, 504):
                    time.sleep(attempt * 3)
                    continue
                resp.raise_for_status()
                data = resp.json()
                log(f"✓ {len(data['elements'])} elements in {time.time() - t0:.1f}s")
                with open(cf, "w") as f:
                    json.dump(data, f)
                return data
            except requests.exceptions.Timeout:
                time.sleep(attempt * 3)
            except requests.exceptions.RequestException:
                break

    raise RuntimeError("All Overpass mirrors failed. Check internet / try later.")
