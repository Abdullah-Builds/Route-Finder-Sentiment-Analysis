# 🗺️ AI Route Finder & Sentiment Analysis

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)
![Algorithm](https://img.shields.io/badge/Algorithm-A%2A%20Search-orange?style=flat)
![ML](https://img.shields.io/badge/ML-TF--IDF%20%2B%20Logistic%20Regression-brightgreen?style=flat&logo=scikit-learn&logoColor=white)
![Map](https://img.shields.io/badge/Maps-OpenStreetMap-7EBC6F?style=flat&logo=openstreetmap&logoColor=white)
![License](https://img.shields.io/badge/License-Open%20Source-blue?style=flat)
![University](https://img.shields.io/badge/FAST--NUCES-Karachi-red?style=flat)

A dual-component AI project from **FAST-NUCES Karachi** that demonstrates practical applications of informed search and machine learning:

- **Task 1** — A\* pathfinding on live OpenStreetMap data with step-by-step browser visualization
- **Task 2** — Reddit sentiment analysis using TF-IDF + Logistic Regression

---

## ✨ Features

### Route Finder (A\*)
- Hand-coded A\* with binary min-heap and lazy deletion — no external graph libraries
- Custom KD-Tree for **O(log n)** nearest-node lookup instead of brute-force O(n) scan
- Haversine-based admissible heuristic guaranteeing optimal paths
- Supports **drive**, **walk**, and **bike** networks via OSM Overpass API
- Disk-cached OSM data to avoid redundant API calls
- Interactive **Folium map** with route overlay and turn-by-turn directions
- Optional A\* execution trace export for the step-by-step browser visualizer

### A\* Visualizer
- Animated, frame-by-frame replay of the full A\* search in the browser
- Colour-coded nodes: **green** = start, **red** = goal, **blue** = expanded, **yellow** = open frontier
- g-score / f-score floated next to nodes as they're assigned
- Scrub, pause, and step controls — no extra dependencies beyond Python 3

### Sentiment Analyzer (Reddit)
- Fetches up to 100 Reddit posts for any topic via RSS
- TF-IDF vectorizer + Logistic Regression pipeline (`sklearn`)
- Outputs a self-contained HTML report — positive (green), negative (red), neutral (grey)

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- A modern web browser (Chrome, Firefox, Edge)

### Installation

```bash
git clone https://github.com/Abdullah-Builds/Route-Finder-Sentiment-Analysis.
cd Route-Finder-Sentiment-Analysis.
pip install requests folium scikit-learn feedparser python-dotenv
```

### Optional: TomTom Traffic API

For live traffic-aware edge weights, create a `.env` file in the project root:

```env
TOMTOM_API_KEY=your_api_key_here
```

Get a free key at [developer.tomtom.com](https://developer.tomtom.com). Without it, the router falls back to static speed defaults — routes still work correctly.

---

## 🧭 Usage

### Task 1 — Run the Route Finder

```bash
python task1.py
```

You will be prompted for:

```
Enter start location : Dolmen Mall Clifton Karachi
Enter end   location : Jinnah International Airport Karachi
Network type [drive] : drive
Record A* trace for visualization? [y/N] : y
```

**Outputs:**
- `route_map.html` — interactive Folium map, opens automatically in your browser
- `astar_trace.json` — full search trace (generated if you answered `y` above)
- Turn-by-turn directions printed to the terminal

### Task 1 — View the A\* Visualizer

After generating `astar_trace.json`, launch the step-by-step animation:

```bash
python view_animation.py
```

This starts a local HTTP server on port 8000 and opens `astar_visualizer.html` in your browser automatically. Press **Ctrl+C** in the terminal when finished.

> **Why a local server?** Browsers block loading the 23 MB trace file directly from disk (CORS restriction). The server bypasses this cleanly.

### Task 2 — Reddit Sentiment Analysis

```bash
python task2.py
```

You will be prompted for a topic:

```
Enter topic: artificial intelligence
```

**Output:** `reddit_sentiment.html` — open this file in any browser to see the colour-coded sentiment table.

---

## 📁 Project Structure

```
.
├── task1.py               # A* route finder (core algorithm + map output)
├── task2.py               # Reddit sentiment analysis
├── view_animation.py      # Local server to launch the A* visualizer
├── astar_visualizer.html  # Browser-based step-by-step A* animation
├── astar_trace.json       # Generated trace data (created after running task1.py)
├── route_map.html         # Generated route map (created after running task1.py)
├── osm_cache/             # Cached OSM Overpass responses (auto-created)
├── graph_cache/           # Cached graph files (auto-created)
├── cache/                 # General request cache (auto-created)
├── planning.md            # Architecture notes and ML extension ideas
├── project_proposal.txt   # Original project proposal (FAST-NUCES)
└── .env                   # API keys — not committed (add your own)
```

---

## 🔧 How It Works

### A\* Route Finder

1. **Geocoding** — Nominatim converts place names to lat/lon coordinates
2. **OSM Fetch** — Overpass API returns road network data for the bounding box (3 mirrors with retry + disk cache)
3. **Graph Build** — OSM ways are converted to a weighted adjacency list; edge cost = `distance / speed`
4. **KD-Tree** — Built over all routable nodes for fast nearest-node lookup at start/end points
5. **A\* Search** — Haversine heuristic divided by max speed (admissible); binary min-heap open set; lazy deletion for stale entries
6. **Trace Export** — Every node expansion, relaxation, and skip is logged and serialised to JSON for the visualizer

### Sentiment Analysis

1. A small seed corpus (8 examples) is used to train the TF-IDF → Logistic Regression pipeline
2. Reddit RSS feed is parsed for the user's topic (up to 100 posts)
3. Each post (title + summary) is classified as **positive**, **negative**, or **neutral**
4. Results are written to a styled HTML report

---

## 🛠️ Extending the Project

The `planning.md` file contains detailed architectural notes on three planned extensions:

- **Learned edge weights** — XGBoost/MLP regression model predicting time-of-day traffic speeds, replacing static `SPEED_KPH` constants
- **Learned A\* heuristic** — A neural network trained on self-generated A\* trace data to replace the Haversine heuristic with a topology-aware estimate
- **Dual-panel visualizer** — Synchronized abstract graph (D3.js or Cytoscape.js) alongside the real Folium map, with side-by-side heuristic comparison mode

---

## 🐛 Known Limitations

- The sentiment classifier is trained on a minimal seed dataset (8 examples); accuracy on niche topics may be low
- OSM data availability and Overpass API response times vary by region; rural or less-mapped areas may produce incomplete graphs
- The TomTom traffic integration is scaffolded but currently falls back to static speeds (see commented code in `task1.py`)
- Very large bounding boxes (long inter-city routes) may produce large `astar_trace.json` files (>20 MB)

---

## 🤝 Contributing

Contributions are welcome! To get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes with clear messages
4. Open a pull request describing what you changed and why

Please keep pull requests focused — one feature or fix per PR.

---

## 🏫 About

Developed as an AI/ML course project at **FAST National University of Computer and Emerging Sciences, Karachi Campus** (April 2026).

**Maintainer:** [Abdullah-Builds](https://github.com/Abdullah-Builds)

---

## 📄 License

This project is open source. See the repository for license details.
