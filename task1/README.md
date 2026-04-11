# A* Route Finder

A pure Python A* pathfinding implementation with a Streamlit frontend.

## Project Structure

```
astar_route_finder/
├── core/
│   ├── __init__.py
│   ├── haversine.py        # Haversine distance formula
│   ├── kdtree.py           # Hand-coded KD-Tree (O(log n) nearest-node)
│   ├── geocoding.py        # Nominatim geocoder
│   ├── osm_fetcher.py      # Overpass API fetch with caching & retries
│   ├── graph_builder.py    # OSM → adjacency list graph
│   ├── astar.py            # A* algorithm with binary min-heap
│   ├── bbox.py             # Bounding-box calculator
│   └── map_renderer.py     # Folium map + turn-by-turn directions
├── ui/
│   └── streamlit_app.py    # Streamlit frontend
├── cache_store/            # Disk cache for OSM data (auto-created)
├── outputs/                # Saved route maps (auto-created)
├── requirements.txt
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run ui/streamlit_app.py
```
