"""
Compute a padded bounding box around two lat/lon points.
Padding is 10 % of the straight-line distance, clamped to [0.5, 2.0] km.
"""

import math
from .haversine import haversine


def compute_bbox(lat1, lon1, lat2, lon2):
    sl_km = haversine(lat1, lon1, lat2, lon2) / 1000
    pad_km = max(0.5, min(2.0, sl_km * 0.10))
    pad_lat = pad_km / 111.0
    pad_lon = pad_km / (111.0 * max(math.cos(math.radians((lat1 + lat2) / 2)), 1e-9))
    return (
        max(lat1, lat2) + pad_lat,
        min(lat1, lat2) - pad_lat,
        max(lon1, lon2) + pad_lon,
        min(lon1, lon2) - pad_lon,
    )
