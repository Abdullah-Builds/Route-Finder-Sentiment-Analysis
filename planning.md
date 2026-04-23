# Part 1: Learned Edge Weights (ML on Speed Prediction)

## The Core Problem with Your Current Code

Your `SPEED_KPH` dict is a global constant — every residential road in Karachi gets 30 km/h whether it's 3am on a Sunday or 5pm on a Friday during rush hour near Tariq Road. This is obviously wrong. The goal is to make edge costs dynamic and data-driven.

## What You're Actually Training

A regression model where the input is a feature vector describing a road segment at a specific time, and the output is the predicted actual travel speed in km/h. That speed then replaces your hardcoded value when computing `cost = dist / speed` for each edge in the graph.

## Feature Engineering — What Goes Into the Model

### Road features (from OSM tags, you already have these):

- road_type — one-hot encoded (residential, primary, motorway, etc.)
- num_lanes — higher lanes usually means higher speed
- has_traffic_signals — intersections with signals slow you down
- is_oneway — correlates with arterial roads, higher speeds
- max_speed_tag — OSM sometimes has explicit speed limits
- road_length — longer segments tend to be faster (highway stretches)

### Temporal features (derived from a timestamp):

- hour_of_day — 0–23, encoded cyclically as sin(2π*hour/24) and cos(2π*hour/24) so that hour 23 and hour 0 are "close" to each other numerically
- day_of_week — weekday vs weekend matters enormously
- is_rush_hour — binary flag for 7–9am and 4–7pm
- is_friday_prayer — in Karachi context, Friday 12–2pm is uniquely bad
- month — seasonal variation if your data spans a year

### Spatial context features (computed from the graph):

- nearby_poi_density — count of shops, offices within 200m (OSM has this)
- intersection_degree — how many roads meet at start/end of this edge
- distance_to_city_center — roads closer to downtown are slower

## Where to Get Training Data

### Option A — OpenTraffic (recommended starting point)

This is GPS trace data contributed by Mapbox, Grab, and others, aggregated per OSM road segment with hourly speed profiles. It's genuinely free and gives you real observed speeds keyed to OSM way IDs — the exact same IDs your graph builder already creates. The limitation is coverage; Pakistani cities have sparse data, so you may need to supplement.

### Option B — HERE Traffic API

Free tier gives you 250k API calls/month. You query it for a specific lat/lon and time, get current and historical speed. You'd programmatically sample random road segments from your OSM graph, query HERE at different simulated timestamps, and collect (features → speed) pairs.

### Option C — Synthetic simulation (most controllable)

This is actually the most practical for a project. You define realistic speed profiles yourself based on domain knowledge — peak hours slow everything by 40%, rain reduces speeds by 20%, etc. — then add Gaussian noise. You train the model on this synthetic data. This sounds like "cheating" but it's a completely valid approach and what many academic papers do. The ML model still learns real patterns; you're just controlling the ground truth.

### Option D — OSRM comparison

Run the same route through OSRM (which uses real-world calibrated speeds) and your A\*. Record the ratio of OSRM time vs your time per road segment. That ratio trains a correction factor model.

## The Training Pipeline

You run your OSM graph builder for a city, iterate over every edge in the graph, and for each edge generate N training samples — one per (time_of_day, day_of_week) combination. Each sample has the road features plus temporal features as X, and the target speed (from whichever data source) as Y. You end up with a DataFrame with maybe 500k rows for a medium-sized city.

You train an XGBoost regressor (or a 3-layer sklearn MLP) on this. XGBoost is recommended first because it handles the mix of categorical and continuous features naturally, trains fast, is interpretable via feature importance plots, and rarely overfits on tabular data.

## How It Plugs Into A\*

In your current `build_graph` function, where you compute `spd = SPEED_KPH.get(hw, 30) / 3.6`, you instead call `model.predict(feature_vector)`. The rest of the A\* is completely unchanged. The model only affects edge cost; the algorithm, graph structure, and heuristic stay identical.

The UX implication: your app now has a time picker. User selects "depart at 5:30pm Friday" — you build the feature vectors with those temporal values, predict speeds, build the graph, run A\*. The route shown is time-aware.

---

# Part 2: Learned Heuristic (ML Replacing Haversine)

## Why Haversine Is a Weak Heuristic on Real Roads

Haversine measures straight-line distance through the air. But real roads have detours around rivers, one-way systems, highway ramps, dead ends, and urban blocks. A node that is 500m "as the crow flies" from the goal might be 2km by road because there's a river between them. Haversine doesn't know this — it always underestimates, which is correct for admissibility, but it underestimates wildly in complex urban areas.

A better heuristic would know: "from this specific node in this specific city, given the road network topology around me, the true cost to goal is approximately X." That's what you train.

## Data Generation — Self-Supervised from Your Own A\*

This is elegant: your existing A* generates its own training data.* You don't need any external dataset.

The process: pick a city, build the OSM graph once. Then randomly sample 5,000–10,000 (origin, destination) pairs. For each pair, run your current A\*. During the run, every time you expand a node, record: the node's features, the goal's features, and what the g_score was at that node when the goal was finally reached minus that node's g_score — that difference is the true remaining cost from that node to the goal along the optimal path.

You accumulate millions of (node_features, goal_features → true_remaining_cost) training examples from these runs. The model learns the topology implicitly.

## Features for the Heuristic Model

### For the current node:

- lat, lon
- degree (how many edges connect here)
- road_type of best adjacent edge
- avg_neighbor_speed — average speed of adjacent road segments

### For the goal node:

- Same features

### Relational features (current node relative to goal):

- haversine_distance — you include this as a feature, not as the heuristic itself; the model learns to correct it
- delta_lat, delta_lon — directional information
- bearing — angle from current node to goal

### Graph topology features:

- road_density_in_corridor — number of road segments within a bounding box between current and goal
- water_body_crossing_probability — if there's a river between them, cost will be much higher (from OSM relation data)

## Training and Admissibility

The critical constraint: your learned h(n) must never overestimate true cost, or A\* loses its optimality guarantee. A neural network trained naively will sometimes overestimate.

### Solutions:

- Scale the output down — multiply predicted h(n) by 0.9. You slightly underestimate on average, preserving admissibility, at the cost of being less tight.
- Train to predict a lower bound — use quantile regression targeting the 10th percentile of true cost instead of the mean.
- Use WA* — if you're willing to accept bounded suboptimality (say within 5% of optimal), you can use the raw prediction as h(n) inside weighted A*, and the bound is mathematically guaranteed.

The last option is actually what TransPath does — TransPath predicts a correction factor defined as the ratio of the available instance-independent heuristic to the perfect heuristic, then plugs this into WA\* to use individual weights per node rather than a single constant weight. AIRI

---

# Part 3: The Visualization Architecture

This is where you can really differentiate the project visually. The idea of a separate abstract graph component alongside the real map is excellent and here's how to think about it properly.

## Two-Panel Architecture

### Left panel — The Real Map:

Your existing Folium/Leaflet map. Shows actual streets, rendered route, start/end markers. This is the "output" view — what a user cares about.

### Right panel — The Abstract Graph:

A force-directed or fixed-coordinate graph visualization showing the OSM nodes as circles and edges as lines. This is the "algorithm" view — what a CS student cares about. It's not trying to look like a map; it's trying to show the search process.

## What the Abstract Graph Shows

The abstract graph doesn't need to show every node — your OSM graph might have 50,000 nodes which is unrenderable. You have two options:

### Option A — Subgraph around the path:

Extract only the nodes within N hops of the discovered path, plus all nodes that were in the open/closed set during A\* search. This gives you maybe 500–2000 nodes — renderable.

### Option B — Simplified topology graph:

Reduce the OSM graph to only intersection nodes (nodes with degree ≥ 3), hiding intermediate road nodes. This dramatically reduces size while preserving the connectivity structure.

## The Animation Sequence

This is the compelling part. You record the full A\* execution trace — every open set push, every node expansion, every path update — and replay it as an animation.

Frame by frame:

- Graph starts with start node highlighted green, goal highlighted red
- As A\* expands nodes, they light up in one color (say blue = "visited/closed")
- Nodes in the open set pulse in a different color (say yellow = "frontier/considering")
- The g-score and f-score values float next to nodes as they're assigned
- When the goal is found, the path nodes light up red and you see the backtracking happen in reverse
- The animation can be scrubbed — user can pause, step forward/backward frame by frame

Synchronized with the real map: When you click a node in the abstract graph, the corresponding real-world location highlights on the map. This is the "aha moment" — users understand that these abstract dots represent real intersections.

## Showing the ML Impact

This is the key visualization that makes the ML work tangible:

Comparison mode: Run A\* twice — once with haversine heuristic, once with your learned heuristic. Show both animations simultaneously side by side. The learned heuristic's animation should visibly expand fewer nodes (less blue area), while finding the same or comparable path. You're literally showing why the ML heuristic is better in a way that's immediately intuitive.

For the speed prediction model: you color the edges on both the real map and abstract graph by predicted speed — red for slow, green for fast, based on the selected departure time. Changing the time slider dynamically recolors the graph in real time, before even running the route.

## Technology Recommendation for the Abstract Graph

D3.js is the natural fit — it has force simulation, zoom/pan, smooth transitions, and is browser-native so it sits alongside your map without additional dependencies. You'd export the A\* trace as a JSON file from Python, load it in the browser, and drive the animation with D3's timer/transition system.

Alternatively, Cytoscape.js is purpose-built for graph visualization and has built-in animation APIs that are simpler than D3's lower-level primitives.

The overall architecture becomes: Python backend runs A\* and ML inference, exports a trace.json with the full execution log, and a single HTML page loads both Leaflet (map) and D3 (graph), consuming that trace file.
