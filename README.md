# Route Finder Search Animation

This visualizer allows you to see the A* search algorithm in action, step by step, as it explores the graph to find the shortest path between your selected locations.

## How to Run the Animation

To view the animation, run the following command in your terminal:

```bash
python3 view_animation.py
```

### What this script does:
1.  **Starts a Local Server**: To bypass browser security restrictions (CORS) when loading the 23MB trace data file (`astar_trace.json`).
2.  **Opens the Visualizer**: Automatically launches `astar_visualizer.html` in your default web browser at `http://localhost:8000`.
3.  **Monitors Progress**: Keeps the server running until you are finished.

### Controls:
- **Ctrl + C**: Stop the local server in your terminal when you are done viewing.

## Requirements
- Python 3.x
- A modern web browser (Chrome, Firefox, Edge, etc.)
