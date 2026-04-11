"""
Map rendering (Folium) and turn-by-turn direction generation.

save_map()      → writes route_map.html, returns the file path
get_directions() → returns a list of (step, road_name, dist_km) tuples
"""

import folium


def save_map(nodes, path, o_name, d_name, dist_m, time_s, out="route_map.html"):
    coords = [(nodes[n][0], nodes[n][1]) for n in path]
    centre = (
        (coords[0][0] + coords[-1][0]) / 2,
        (coords[0][1] + coords[-1][1]) / 2,
    )
    m = folium.Map(location=centre, zoom_start=13, tiles="OpenStreetMap")
    folium.PolyLine(coords, color="#E63946", weight=5, opacity=0.85).add_to(m)
    folium.Marker(
        coords[0],
        popup=f"START: {o_name}",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(m)
    folium.Marker(
        coords[-1],
        popup=f"END: {d_name}",
        icon=folium.Icon(color="red", icon="flag", prefix="fa"),
    ).add_to(m)

    mins, secs = int(time_s // 60), int(time_s % 60)
    m.get_root().html.add_child(
        folium.Element(f"""
    <div style="position:fixed;top:10px;right:10px;z-index:9999;
      background:rgba(255,255,255,.93);padding:12px 18px;border-radius:10px;
      box-shadow:0 2px 8px rgba(0,0,0,.25);font-family:sans-serif;
      font-size:14px;line-height:1.8">
      <b>🗺 A* Route Finder</b><br>
      <span style="color:#555">From:</span> {o_name}<br>
      <span style="color:#555">To:</span> {d_name}<br>
      <hr style="margin:6px 0">
      <span style="color:#E63946;font-size:16px;font-weight:bold">
        📏 {dist_m / 1000:.2f} km</span><br>
      <span style="color:#457B9D">⏱ ~{mins}m {secs:02d}s</span>
    </div>""")
    )
    m.save(out)
    return out


def get_directions(path, graph):
    """
    Build turn-by-turn directions from the path.
    Returns a list of dicts: [{step, road, distance_km}]
    """
    directions = []
    step, prev_name, seg_d = 1, None, 0.0

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        name, dist_m = "unnamed", 0.0
        for nb, _, dm, nm in graph.get(u, []):
            if nb == v:
                name, dist_m = nm, dm
                break

        if name == prev_name:
            seg_d += dist_m
        else:
            if prev_name is not None:
                directions.append(
                    {"step": step, "road": prev_name, "distance_km": seg_d / 1000}
                )
                step += 1
            prev_name, seg_d = name, dist_m

    if prev_name:
        directions.append(
            {"step": step, "road": prev_name, "distance_km": seg_d / 1000}
        )

    return directions
