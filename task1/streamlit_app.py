"""
Streamlit frontend for the A* Route Finder.
Run with:  streamlit run ui/streamlit_app.py
"""

from core import (
    astar,
    NoPathError,
    compute_bbox,
    fetch_osm,
    build_graph,
    geocode,
    get_directions,
    haversine,
    kd_build,
    kd_nearest,
    save_map,
)
import os
import sys
import time

import streamlit as st

# Make the project root importable regardless of CWD
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="A* Route Finder",
    page_icon="🗺️",
    layout="wide",
)

# ── Styles ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 14px 20px;
        margin-bottom: 10px;
        border-left: 4px solid #E63946;
    }
    .metric-value { font-size: 22px; font-weight: 700; color: #E63946; }
    .metric-label { font-size: 13px; color: #666; }
    .step-row {
        display: flex; justify-content: space-between;
        padding: 6px 0; border-bottom: 1px solid #eee;
        font-size: 14px;
    }
    .step-num { color: #457B9D; font-weight: 600; min-width: 30px; }
    .step-road { flex: 1; padding: 0 10px; }
    .step-dist { color: #888; white-space: nowrap; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🗺️ A* Route Finder")
st.caption(
    "Pure Python A\\* pathfinding · Haversine distance · Hand-coded KD-Tree · "
    "OSM data via Overpass API · Folium map rendering"
)
st.divider()

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Route Settings")

    origin = st.text_input(
        "📍 Start location", placeholder="e.g. Karachi, Pakistan")
    destination = st.text_input(
        "🏁 End location", placeholder="e.g. Lahore, Pakistan")

    net = st.radio(
        "🚦 Network type",
        options=["drive", "walk", "bike"],
        index=0,
        horizontal=True,
        format_func=lambda x: {"drive": "🚗 Drive",
                               "walk": "🚶 Walk", "bike": "🚴 Bike"}[x],
    )

    find_btn = st.button("🔍 Find Route", type="primary",
                         use_container_width=True)

    st.divider()
    st.markdown(
        """
        **How it works**
        1. Geocodes your places via Nominatim
        2. Fetches OSM road network via Overpass
        3. Builds an adjacency-list graph
        4. KD-Tree finds nearest routable nodes
        5. A\\* finds the optimal path
        6. Folium renders the route map
        """
    )

# ── Main panel ────────────────────────────────────────────────────────────────
if not find_btn:
    st.info(
        "👈  Enter a start and end location in the sidebar, then click **Find Route**.")
    st.stop()

if not origin.strip() or not destination.strip():
    st.error("Please enter both a start and an end location.")
    st.stop()

# ── Progress + pipeline ───────────────────────────────────────────────────────
log_lines = []
log_box = st.empty()


def log(msg: str):
    log_lines.append(msg)
    log_box.code("\n".join(log_lines), language=None)


progress = st.progress(0, text="Starting …")

try:
    # Step 1 – Geocode
    progress.progress(10, text="📍 Geocoding locations …")
    log("📍 Geocoding …")
    olat, olon = geocode(origin)
    dlat, dlon = geocode(destination)
    sl_km = haversine(olat, olon, dlat, dlon) / 1000
    log(f"   Start → {olat:.5f}, {olon:.5f}")
    log(f"   End   → {dlat:.5f}, {dlon:.5f}")
    log(f"   Straight-line: {sl_km:.2f} km")

    # Step 2 – Fetch OSM
    progress.progress(25, text="🌐 Fetching road network …")
    log(f"\n🌐 Fetching OSM ({net}) …")
    north, south, east, west = compute_bbox(olat, olon, dlat, dlon)
    osm_data = fetch_osm(north, south, east, west, net, log=log)

    # Step 3 – Build graph
    progress.progress(50, text="🔧 Building graph …")
    log("\n🔧 Building graph …")
    t0 = time.time()
    nodes, graph = build_graph(osm_data, net)
    log(f"   Built in {time.time() - t0:.2f}s  |  "
        f"{len(nodes):,} nodes  |  {sum(len(e) for e in graph.values()):,} edges")

    if not graph:
        st.error("❌ No routable roads found in this area.")
        st.stop()

    # Step 4 – KD-Tree
    progress.progress(65, text="🌲 Building KD-Tree …")
    log("\n🌲 Building KD-Tree …")
    t1 = time.time()
    routable = {nid: nodes[nid] for nid in graph}
    kd_root = kd_build(routable)
    log(f"   Built in {time.time() - t1:.3f}s  ({len(routable):,} routable nodes)")

    start_id = kd_nearest(kd_root, olat, olon)
    goal_id = kd_nearest(kd_root, dlat, dlon)
    log(f"   Start node: {start_id}  {nodes[start_id]}")
    log(f"   Goal  node: {goal_id}  {nodes[goal_id]}")

    # Step 5 – A*
    progress.progress(80, text="🔍 Running A* …")
    log("\n🔍 Running A* …")
    t2 = time.time()
    path, total_dist, total_time, explored = astar(
        nodes, graph, start_id, goal_id)
    elapsed = time.time() - t2
    mins, secs = int(total_time // 60), int(total_time % 60)
    log(f"   ✓ Finished in     {elapsed:.3f}s")
    log(f"   ✓ Nodes explored  {explored:,}")
    log(f"   ✓ Path length     {len(path)} nodes")
    log(f"   ✓ Distance        {total_dist / 1000:.2f} km")
    log(f"   ✓ Travel time     ~{mins}m {secs:02d}s")

    # Step 6 – Map
    progress.progress(93, text="🗺️ Rendering map …")
    log("\n🗺️ Saving map …")
    os.makedirs(os.path.join(os.path.dirname(
        __file__), "..", "outputs"), exist_ok=True)
    map_path = os.path.join(
        os.path.dirname(__file__), "..", "outputs", "route_map.html"
    )
    save_map(nodes, path, origin, destination,
             total_dist, total_time, out=map_path)
    log(f"   Map saved → {map_path}")

    progress.progress(100, text="✅ Done!")

except ValueError as e:
    st.error(f"❌ Geocoding failed: {e}")
    st.stop()
except NoPathError as e:
    st.error(f"❌ {e}")
    st.stop()
except RuntimeError as e:
    st.error(f"❌ {e}")
    st.stop()

# ── Results ───────────────────────────────────────────────────────────────────
st.divider()
st.subheader("📊 Route Summary")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("📏 Distance", f"{total_dist / 1000:.2f} km")
with c2:
    st.metric("⏱️ Est. Travel Time", f"{mins}m {secs:02d}s")
with c3:
    st.metric("🔍 Nodes Explored", f"{explored:,}")
with c4:
    st.metric("📐 Straight-line", f"{sl_km:.2f} km")

st.divider()

# ── Map embed ──────────────────────────────────────────────────────────────────
st.subheader("🗺️ Route Map")
with open(map_path, "r", encoding="utf-8") as f:
    map_html = f.read()

st.components.v1.html(map_html, height=520, scrolling=False)

col_dl, _ = st.columns([1, 3])
with col_dl:
    with open(map_path, "rb") as f:
        st.download_button(
            label="⬇️ Download Map (HTML)",
            data=f,
            file_name="route_map.html",
            mime="text/html",
            use_container_width=True,
        )

# ── Turn-by-turn ───────────────────────────────────────────────────────────────
st.divider()
st.subheader("🧭 Turn-by-Turn Directions")

directions = get_directions(path, graph)

if directions:
    header_cols = st.columns([0.5, 5, 1.5])
    header_cols[0].markdown("**#**")
    header_cols[1].markdown("**Road**")
    header_cols[2].markdown("**Distance**")

    for d in directions:
        cols = st.columns([0.5, 5, 1.5])
        cols[0].write(d["step"])
        cols[1].write(d["road"])
        cols[2].write(f"{d['distance_km']:.2f} km")
else:
    st.info("No direction data available for this route.")
