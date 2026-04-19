"""
A* Route Finder — Pure Implementation, Optimized
=================================================
All core logic is hand-coded:
  • Haversine distance formula
  • Nominatim geocoding (plain HTTP)
  • Overpass API fetch (plain HTTP, 3 mirrors, retry)
  • Graph built manually from OSM ways
  • KD-Tree built from scratch for O(log n) nearest-node lookup
  • A* with binary min-heap (heapq), lazy deletion, admissible heuristic
  • Folium used only for map rendering

Requirements:  pip install requests folium
"""

import heapq
import math
import time
import hashlib
import json
import os
import webbrowser
import requests
import folium
import os
from dotenv import load_dotenv
load_dotenv();
API_KEY=os.getenv("TOMTOM_API_KEY");
#Url for tomtom api
url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/xml"

# ══════════════════════════════════════════════════════════════════════════════
#  1. HAVERSINE
# ══════════════════════════════════════════════════════════════════════════════


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# ══════════════════════════════════════════════════════════════════════════════
#  2. KD-TREE  (hand-coded, 2D on lat/lon)
#  Replaces the O(n) brute-force nearest-node scan with O(log n) search.
# ══════════════════════════════════════════════════════════════════════════════


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
    node.left = _kd_build(points[:mid],       depth + 1)
    node.right = _kd_build(points[mid + 1:],   depth + 1)
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
    near, far = (root.left, root.right) if diff <= 0 else (
        root.right, root.left)

    _kd_nearest(near, lat, lon, depth + 1, best)

    # Only search the far side if it could contain a closer point.
    # We compare the axis-split distance (in degrees) converted to metres.
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

# ══════════════════════════════════════════════════════════════════════════════
#  3. GEOCODING  (Nominatim)
# ══════════════════════════════════════════════════════════════════════════════


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

# ══════════════════════════════════════════════════════════════════════════════
#  4. OVERPASS FETCH  (3 mirrors, retry, disk cache)
# ══════════════════════════════════════════════════════════════════════════════


MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
CACHE_DIR = "osm_cache"

HIGHWAY_TAGS = {
    "drive": ("motorway|trunk|primary|secondary|tertiary|unclassified|"
              "residential|motorway_link|trunk_link|primary_link|"
              "secondary_link|tertiary_link|living_street|road"),
    "walk":  "primary|secondary|tertiary|unclassified|residential|living_street|pedestrian|footway|path|steps|track",
    "bike":  "primary|secondary|tertiary|unclassified|residential|living_street|cycleway|path|track",
}

SPEED_KPH = {
    "motorway": 110, "trunk": 90, "primary": 60, "secondary": 50, "tertiary": 40,
    "unclassified": 30, "residential": 30, "motorway_link": 60, "trunk_link": 60,
    "primary_link": 45, "secondary_link": 35, "tertiary_link": 25,
    "living_street": 10, "road": 30, "cycleway": 20, "footway": 5,
    "path": 5, "steps": 2, "track": 20, "pedestrian": 5,
}
def get_midpoint(lat1, lon1, lat2, lon2):
    """Return midpoint coordinates for a segment."""
    return (lat1 + lat2) / 2, (lon1 + lon2) / 2
# Add at module level
_traffic_cache = {}  # Simple in-memory cache: "lat,lon" → speed_kph

def get_traffic_speed(lat1, lon1, lat2, lon2, net):
    """
    Query TomTom for current speed on a road segment.
    Falls back to default SPEED_KPH if API fails or is unavailable.
    """
    if not API_KEY:
        print("Could not find api key")
        return SPEED_KPH.get("residential", 30) / 3.6  # fallback to m/s
    
    # Use midpoint for the query
    qlat, qlon = get_midpoint(lat1, lon1, lat2, lon2)
    cache_key = f"{qlat:.5f},{qlon:.5f}"
    
    if cache_key in _traffic_cache:
        return _traffic_cache[cache_key] / 3.6  # return m/s
    
    try:
        params = {
            "point": f"{qlat},{qlon}",
            "key": API_KEY,
            "unit": "metric"
        }
        resp = requests.get(
            "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/xml",
            params=params,
            timeout=8
        )
        if resp.status_code == 200:
            # Parse XML response (TomTom returns XML, not JSON)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.content)
            # Namespace handling for TomTom XML
            ns = {"tt": "http://tomtom.com/schemas/traffic/4.0"}
            speed_elem = root.find(".//tt:currentSpeed", ns)
            if speed_elem is not None:
                speed_kph = float(speed_elem.text)
                _traffic_cache[cache_key] = speed_kph
                return speed_kph / 3.6  # convert to m/s
    except Exception:
        print("Exception occured")
        pass  # Silently fall back to default speed
    
    # Fallback: use static speed based on highway type
    # You could pass highway type here for smarter fallback
    return SPEED_KPH.get("residential", 30) / 3.6


def _cache_file(bbox, net):
    key = "".join(f"{x:.5f}" for x in bbox) + net
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{h}.json")


def fetch_osm(north, south, east, west, net="drive"):
    cf = _cache_file((north, south, east, west), net)
    if os.path.exists(cf):
        print("   ✓ Loaded from disk cache")
        with open(cf) as f:
            return json.load(f)

    tags = HIGHWAY_TAGS[net]
    query = (f"[out:json][timeout:55];"
             f"(way[\"highway\"~\"^({tags})$\"]"
             f"({south:.6f},{west:.6f},{north:.6f},{east:.6f});>;);"
             f"out body;")

    for mirror in MIRRORS:
        for attempt in range(1, 4):
            try:
                print(f"   ↓ {mirror.split('/')[2]}  attempt {attempt}/3 …")
                t0 = time.time()
                resp = requests.post(mirror, data={"data": query},
                                     timeout=70,
                                     headers={"User-Agent": "AStarRouteFinder/3.0"})
                if resp.status_code in (502, 503, 504):
                    time.sleep(attempt * 3)
                    continue
                resp.raise_for_status()
                data = resp.json()
                print(
                    f"   ✓ {len(data['elements'])} elements in {time.time()-t0:.1f}s")
                with open(cf, "w") as f:
                    json.dump(data, f)
                return data
            except requests.exceptions.Timeout:
                time.sleep(attempt * 3)
            except requests.exceptions.RequestException:
                break
    raise RuntimeError(
        "All Overpass mirrors failed. Check internet / try later.")

# ══════════════════════════════════════════════════════════════════════════════
#  5. GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════════════════


def build_graph(osm_data, net="drive"):
    """
    Returns:
      nodes  : { id -> (lat, lon) }
      graph  : { id -> [(neighbour_id, cost_sec, dist_m, road_name)] }
    """
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
        oneway = (tags.get("oneway", "no") in (
            "yes", "1", "true") and net == "drive")
        
        # params = {
        #     "point": f"{el['bounds']['minlat']},{el['bounds']['minlon']}",
        #     "key": API_KEY
            
            
        # }
        # traffic_data = requests.get(url, params= params);
        # cur_speed = traffic_data["flowSegmentData"]["currentSpeed"];
        # print(traffic_data);
        # print("Cur speed is: ", cur_speed);
        spd = ( 30) / 3.6      # m/s

        for i in range(len(wn)-1):
            u, v = wn[i], wn[i+1]
            if u not in nodes or v not in nodes:
                continue
            dist = haversine(*nodes[u], *nodes[v])
            lat1, lon1 = nodes[u]
            lat2, lon2 = nodes[v]
            # spd_mps = get_traffic_speed(lat1, lon1, lat2, lon2, net)
            spd_mps=30#hardcoded for testing
            cost = dist / spd_mps
            graph.setdefault(u, []).append((v, cost, dist, name))
            if not oneway:
                graph.setdefault(v, []).append((u, cost, dist, name))

    print(f"   ✓ {len(nodes):,} nodes  |  "
          f"{sum(len(e) for e in graph.values()):,} edges")
    return nodes, graph

# ══════════════════════════════════════════════════════════════════════════════
#  6. A*  — pure hand-coded implementation
# ══════════════════════════════════════════════════════════════════════════════


class NoPathError(Exception):
    pass


def astar(nodes, graph, start_id, goal_id, record_trace: bool=True):
    """
     
    Accepts:
      nodes  : { id -> (lat, lon) }
      graph  : { id -> [(neighbour_id, cost_sec, dist_m, road_name)] }
    
    Hand-coded A* shortest path.

    Open set  : binary min-heap  →  (f_score, g_score, counter, node_id)
    g_score   : dict  node_id → best cost (seconds) found so far
    came_from : dict  node_id → (parent_id, road_name, dist_m)
    closed    : set   of fully expanded node ids
    Lazy deletion: stale heap entries are skipped when popped.

    Heuristic h(n) = haversine(n, goal) / max_speed
    Admissible (never overestimates) → A* returns optimal path.
    """
    frames = []
    touched_nodes = {}
    touched_edges = []
    step = 0;
    def _touch_node(nid):
        if nid not in touched_nodes:
            lat, lon = nodes[nid];
            touched_nodes[nid] = {"lat": lat, "lon": lon};
        
    def _add_frame(frame:dict):
        frame["step"] = step;
        frames.append(frame);
    
    if start_id == goal_id:
        return [start_id], 0.0, 0.0, 0

    glat, glon = nodes[goal_id]
    MAX_SPD = 130 / 3.6              # m/s — upper-bound speed for heuristic

    def h(nid):
        lat, lon = nodes[nid]
        return haversine(lat, lon, glat, glon) / MAX_SPD

    g_score = {start_id: 0.0}
    came_from = {}
    closed = set()
    heap = []
    ctr = 0                       # tie-break counter
    trace = []

    heapq.heappush(heap, (h(start_id), 0.0, ctr, start_id))
    ctr += 1
    explored = 0
    if record_trace:
        _touch_node(start_id)
        _touch_node(goal_id)

    while heap:
        f, g, _, cur = heapq.heappop(heap)
        

        # Lazy deletion — this entry is stale if we've already found a cheaper g
        if g > g_score.get(cur, math.inf):
            continue

        explored += 1
        if record_trace:
            step += 1
            _touch_node(cur)
            _add_frame({
                "type":      "node_expanded",
                "node":      cur,
                "g":         round(g, 3),
                "h":         round(h(cur), 3),
                "f":         round(f, 3),
                "open_size": len(heap),
            })
            

        if cur == goal_id:
            if record_trace:
                step += 1
                _add_frame({
                    "type":       "goal_reached",
                    "node":       cur,
                    "g":          round(g, 3),
                })
            break

        closed.add(cur)

        for edge in graph.get(cur, []):
            if len(edge) == 5:
                nb, edge_cost, edge_dist, road_name, hw = edge
            else:
                nb, edge_cost, edge_dist, road_name = edge
                hw = "road"
            if nb in closed:
                if record_trace:
                    step += 1;
                    _add_frame({
                        "type": "neighbour skipped",
                        "from": cur,
                        "to": nb,
                        "reason": "closed"
                    })
                continue
            
            tg = g + edge_cost
            improved = tg < g_score.get(nb, math.inf)
            if improved:
                h_nb = h(nb)
                
                g_score[nb] = tg
                came_from[nb] = (cur, road_name, edge_dist)
                heapq.heappush(heap, (tg + h(nb), tg, ctr, nb))
                ctr += 1
            if record_trace:
                eu, ev = min(cur, nb), max(cur, nb)
                touched_edges.append({
                    "u":         cur,
                    "v":         nb,
                    "dist_m":    round(edge_dist, 2),
                    "road_name": road_name,
                    "hw":        hw,
                })
                if improved:
                    _add_frame({
                        "type":      "neighbor_relaxed",
                        "from":      cur,
                        "to":        nb,
                        "g":         round(tg, 3),
                        "h":         round(h_nb, 3),
                        "f":         round(tg + h_nb, 3),
                        "dist_m":    round(edge_dist, 2),
                        "road_name": road_name,
                        "improved":  True,
                    })
                else:
                    _add_frame({
                        "type":      "neighbor_skipped",
                        "from":      cur,
                        "to":        nb,
                        "reason":    "not_improved",
                    })
                
    else:
        raise NoPathError("No path found between locations.")

    # Reconstruct path
    path, node = [], goal_id
    while node != start_id:
        path.append(node)
        node = came_from[node][0]
    path.append(start_id)
    path.reverse()

    total_dist = sum(came_from[v][2] for v in path[1:])
    total_time = g_score[goal_id]
    trace = None
    if record_trace:
        step += 1
        _add_frame({
            "type": "path_reconstructed",
            "path": path,
        })
        seen_edges = set()
        unique_edges = []
        for e in touched_edges:
            key = (min(e["u"], e["v"]), max(e["u"], e["v"]))
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)
                
        trace = {
            "meta": {
                "start_id":       start_id,
                "goal_id":        goal_id,
                "start_lat":      nodes[start_id][0],
                "start_lon":      nodes[start_id][1],
                "goal_lat":       nodes[goal_id][0],
                "goal_lon":       nodes[goal_id][1],
                "total_dist_m":   round(total_dist, 2),
                "total_time_s":   round(total_time, 2),
                "nodes_explored": explored,
                "path_length":    len(path),
                "total_frames":   len(frames),
            },
            "graph_nodes":  touched_nodes,
            "graph_edges":  unique_edges,
            "path_nodes":   path,
            "frames":       frames,
        }
    
    return path, total_dist, total_time, explored,trace

def _empty_trace(nodes, start_id, goal_id, path, dist, time_s):
    """Return a minimal valid trace when start == goal."""
    lat, lon = nodes[start_id]
    return {
        "meta": {
            "start_id": start_id, "goal_id": goal_id,
            "start_lat": lat, "start_lon": lon,
            "goal_lat": lat,  "goal_lon": lon,
            "total_dist_m": 0, "total_time_s": 0,
            "nodes_explored": 0, "path_length": 1, "total_frames": 0,
        },
        "graph_nodes": {start_id: {"lat": lat, "lon": lon}},
        "graph_edges": [],
        "path_nodes":  [start_id],
        "frames":      [],
    }
    
def save_trace(trace: dict, path: str = "astar_trace.json"):
    """
    Write the trace dict to a JSON file.
 
    Node ids are Python ints (which are valid JSON).
    The graph_nodes dict uses string keys because JSON only allows string keys.
    We do the int→str conversion here so downstream JS can do
        const node = trace.graph_nodes[nodeId.toString()]
    """
    # Convert int node-id keys to strings for JSON spec compliance
    serialisable = dict(trace)
    serialisable["graph_nodes"] = {
        str(k): v for k, v in trace["graph_nodes"].items()
    }
    # Convert node ids inside frames to plain ints (already are, just be safe)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, separators=(",", ":"))  # compact, no whitespace
 
    size_kb = os.path.getsize(path) / 1024
    print(f"   ✓ Trace saved → {path}  ({size_kb:.1f} KB,  "
          f"{trace['meta']['total_frames']:,} frames,  "
          f"{len(trace['graph_nodes']):,} nodes,  "
          f"{len(trace['graph_edges']):,} edges)")
    return path

# ══════════════════════════════════════════════════════════════════════════════
#  7. BBOX
# ══════════════════════════════════════════════════════════════════════════════


def compute_bbox(lat1, lon1, lat2, lon2):
    sl_km = haversine(lat1, lon1, lat2, lon2) / 1000
    pad_km = max(0.5, min(2.0, sl_km * 0.10))
    pad_lat = pad_km / 111.0
    pad_lon = pad_km / \
        (111.0 * max(math.cos(math.radians((lat1+lat2)/2)), 1e-9))
    return (max(lat1, lat2)+pad_lat, min(lat1, lat2)-pad_lat,
            max(lon1, lon2)+pad_lon, min(lon1, lon2)-pad_lon)

# ══════════════════════════════════════════════════════════════════════════════
#  8. MAP + DIRECTIONS
# ══════════════════════════════════════════════════════════════════════════════


def save_map(nodes, path, o_name, d_name, dist_m, time_s, out="route_map.html"):
    coords = [(nodes[n][0], nodes[n][1]) for n in path]
    centre = ((coords[0][0]+coords[-1][0])/2, (coords[0][1]+coords[-1][1])/2)
    m = folium.Map(location=centre, zoom_start=13, tiles="OpenStreetMap")
    folium.PolyLine(coords, color="#E63946", weight=5, opacity=0.85).add_to(m)
    folium.Marker(coords[0], popup=f"START: {o_name}",
                  icon=folium.Icon(color="green", icon="play", prefix="fa")).add_to(m)
    folium.Marker(coords[-1], popup=f"END: {d_name}",
                  icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)
    mins, secs = int(time_s//60), int(time_s % 60)
    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:fixed;top:10px;right:10px;z-index:9999;
      background:rgba(255,255,255,.93);padding:12px 18px;border-radius:10px;
      box-shadow:0 2px 8px rgba(0,0,0,.25);font-family:sans-serif;
      font-size:14px;line-height:1.8">
      <b>🗺 A* Route Finder</b><br>
      <span style="color:#555">From:</span> {o_name}<br>
      <span style="color:#555">To:</span> {d_name}<br>
      <hr style="margin:6px 0">
      <span style="color:#E63946;font-size:16px;font-weight:bold">
        📏 {dist_m/1000:.2f} km</span><br>
      <span style="color:#457B9D">⏱ ~{mins}m {secs:02d}s</span>
    </div>"""))
    m.save(out)
    return out


def print_directions(path, graph, nodes):
    print("\n─── Turn-by-turn directions ─────────────────────────────")
    # Build edge lookup for direction names
    step, prev_name, seg_d = 1, None, 0.0
    for i in range(len(path)-1):
        u, v = path[i], path[i+1]
        name, dist_m = "unnamed", 0.0
        for nb, _, dm, nm in graph.get(u, []):
            if nb == v:
                name, dist_m = nm, dm
                break
        if name == prev_name:
            seg_d += dist_m
        else:
            if prev_name is not None:
                print(f"  {step:>3}. {prev_name:<45} {seg_d/1000:.2f} km")
                step += 1
            prev_name, seg_d = name, dist_m
    if prev_name:
        print(f"  {step:>3}. {prev_name:<45} {seg_d/1000:.2f} km")
    print("─────────────────────────────────────────────────────────\n")

# ══════════════════════════════════════════════════════════════════════════════
#  9. MAIN
# ══════════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 58)
    print("  🚗  A* Route Finder  —  Pure Implementation v3")
    print("=" * 58)

    origin = input("\nEnter start location : ").strip()
    dest = input("Enter end   location : ").strip()
    print("Network type  →  drive | walk | bike")
    net = input("Network type [drive] : ").strip().lower() or "drive"
    if net not in ("drive", "walk", "bike"):
        net = "drive"
    record = input("Record A* trace for visualization? [y/N] : ").strip().lower()
    record_trace = record in ("y", "yes")

    # Geocode
    print("\n📍 Geocoding …")
    olat, olon = geocode(origin)
    dlat, dlon = geocode(dest)
    print(f"   Start → {olat:.5f}, {olon:.5f}")
    print(f"   End   → {dlat:.5f}, {dlon:.5f}")
    print(f"   Straight-line: {haversine(olat, olon, dlat, dlon)/1000:.2f} km")

    # Bbox + fetch
    north, south, east, west = compute_bbox(olat, olon, dlat, dlon)
    print(f"\n🌐 Fetching OSM ({net}) …")
    try:
        osm_data = fetch_osm(north, south, east, west, net)
    except RuntimeError as e:
        print(f"\n❌ {e}")
        return

    # Build graph
    print("\n🔧 Building graph …")
    t0 = time.time()
    nodes, graph = build_graph(osm_data, net)
    print(f"   Built in {time.time()-t0:.2f}s")

    if not graph:
        print("❌ No routable roads found.")
        return

    # KD-Tree for fast nearest-node lookup  (O(log n) vs O(n))
    print("\n🌲 Building KD-Tree …")
    t1 = time.time()
    routable = {nid: nodes[nid] for nid in graph}   # only nodes with edges
    kd_root = kd_build(routable)
    print(
        f"   Built in {time.time()-t1:.3f}s  ({len(routable):,} routable nodes)")

    start_id = kd_nearest(kd_root, olat, olon)
    goal_id = kd_nearest(kd_root, dlat, dlon)
    print(f"   Start node: {start_id}  {nodes[start_id]}")
    print(f"   Goal  node: {goal_id}  {nodes[goal_id]}")

    # A*
    print("\n🔍 Running A* …")
    t2 = time.time()
    try:
        path, total_dist, total_time, explored,trace = astar(
            nodes, graph, start_id, goal_id,record_trace)
    except NoPathError as e:
        print(f"\n❌ {e}")
        return
    elapsed = time.time() - t2
    mins, secs = int(total_time//60), int(total_time % 60)
    print(f"   ✓ Finished in     {elapsed:.3f}s")
    print(f"   ✓ Nodes explored  {explored:,}")
    print(f"   ✓ Path length     {len(path)} nodes")
    print(f"   ✓ Distance        {total_dist/1000:.2f} km")
    print(f"   ✓ Travel time     ~{mins}m {secs:02d}s")
    if record_trace and trace:
        print("\n💾 Saving trace …")
        save_trace(trace, "astar_trace.json")

    print_directions(path, graph, nodes)

    map_file = save_map(nodes, path, origin, dest, total_dist, total_time)
    print(f"🗺  Map saved → {map_file}")
    try:
        webbrowser.open(f"file://{os.path.abspath(map_file)}")
    except Exception:
        pass
    print(f"\n✅  {total_dist/1000:.2f} km  |  ~{mins}m {secs:02d}s\n")


if __name__ == "__main__":
    main()

#Dolmen Mall Clifton Karachi
#Jinnah International Airport Karachi