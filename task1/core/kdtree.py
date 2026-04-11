"""
Hand-coded 2-D KD-Tree for O(log n) nearest-node lookup.
Replaces O(n) brute-force nearest-node scan.
"""

import math
from .haversine import haversine


class KDNode:
    __slots__ = ("node_id", "lat", "lon", "left", "right")

    def __init__(self, node_id, lat, lon):
        self.node_id = node_id
        self.lat = lat
        self.lon = lon
        self.left = None
        self.right = None


def _kd_build(points, depth=0):
    """
    Recursively build a 2-D KD-Tree.
    points : list of (lat, lon, node_id)
    Alternates splitting axis: depth%2==0 → split on lat, else on lon.
    """
    if not points:
        return None
    axis = depth % 2                        # 0=lat, 1=lon
    points.sort(key=lambda p: p[axis])
    mid = len(points) // 2
    lat, lon, nid = points[mid]
    node = KDNode(nid, lat, lon)
    node.left = _kd_build(points[:mid],      depth + 1)
    node.right = _kd_build(points[mid + 1:], depth + 1)
    return node


def kd_build(routable_nodes: dict):
    """
    Build KD-Tree from {node_id: (lat, lon)}.
    Only includes nodes that have edges (routable).
    """
    pts = [(lat, lon, nid) for nid, (lat, lon) in routable_nodes.items()]
    return _kd_build(pts, depth=0)


def _kd_nearest(root, lat, lon, depth, best):
    """
    Recursive nearest-neighbour search.
    best : [best_dist, best_node_id]  (mutable list for in-place update)
    """
    if root is None:
        return
    d = haversine(lat, lon, root.lat, root.lon)
    if d < best[0]:
        best[0] = d
        best[1] = root.node_id

    axis = depth % 2
    diff = (lat - root.lat) if axis == 0 else (lon - root.lon)
    near, far = (root.left, root.right) if diff <= 0 else (root.right, root.left)

    _kd_nearest(near, lat, lon, depth + 1, best)

    # Only search the far side if it could contain a closer point.
    if axis == 0:
        axis_dist = abs(lat - root.lat) * 111_000
    else:
        axis_dist = abs(lon - root.lon) * 111_000 * math.cos(math.radians(lat))

    if axis_dist < best[0]:
        _kd_nearest(far, lat, lon, depth + 1, best)


def kd_nearest(root, lat, lon):
    best = [math.inf, None]
    _kd_nearest(root, lat, lon, 0, best)
    return best[1]
