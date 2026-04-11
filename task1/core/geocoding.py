"""
Geocoding via Nominatim (OpenStreetMap).
Returns (lat, lon) for a place name string.
"""

import requests


def geocode(place: str):
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "json", "limit": 1},
        headers={"User-Agent": "AStarRouteFinder/3.0"},
        timeout=15,
    )
    resp.raise_for_status()
    hits = resp.json()
    if not hits:
        raise ValueError(f"Cannot geocode: '{place}'")
    return float(hits[0]["lat"]), float(hits[0]["lon"])
