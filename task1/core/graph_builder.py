"""
Builds a weighted adjacency-list graph from raw OSM data.

Returns:
  nodes : { id -> (lat, lon) }
  graph : { id -> [(neighbour_id, cost_sec, dist_m, road_name)] }
"""

from .haversine import haversine
from .osm_fetcher import HIGHWAY_TAGS, SPEED_KPH


def build_graph(osm_data, net="drive"):
    allowed = set(HIGHWAY_TAGS[net].split("|"))
    nodes, graph = {}, {}

    # Index all nodes first in one pass
    for el in osm_data["elements"]:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])

    # Build adjacency list from ways
    for el in osm_data["elements"]:
        if el["type"] != "way":
            continue
        tags = el.get("tags", {})
        hw = tags.get("highway", "")
        if hw not in allowed:
            continue
        wn = el["nodes"]
        name = tags.get("name", tags.get("ref", hw))
        oneway = (
            tags.get("oneway", "no") in ("yes", "1", "true") and net == "drive"
        )
        spd = SPEED_KPH.get(hw, 30) / 3.6      # m/s

        for i in range(len(wn) - 1):
            u, v = wn[i], wn[i + 1]
            if u not in nodes or v not in nodes:
                continue
            dist = haversine(*nodes[u], *nodes[v])
            cost = dist / spd
            graph.setdefault(u, []).append((v, cost, dist, name))
            if not oneway:
                graph.setdefault(v, []).append((u, cost, dist, name))

    return nodes, graph
