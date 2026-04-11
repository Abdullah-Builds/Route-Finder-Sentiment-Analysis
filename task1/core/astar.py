"""
Hand-coded A* shortest-path algorithm.

Open set  : binary min-heap  →  (f_score, g_score, counter, node_id)
g_score   : dict  node_id → best cost (seconds) found so far
came_from : dict  node_id → (parent_id, road_name, dist_m)
closed    : set   of fully expanded node ids
Lazy deletion: stale heap entries are skipped when popped.

Heuristic h(n) = haversine(n, goal) / max_speed
Admissible (never overestimates) → A* returns optimal path.
"""

import heapq
import math

from .haversine import haversine


class NoPathError(Exception):
    pass


def astar(nodes, graph, start_id, goal_id):
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
    ctr = 0                          # tie-break counter

    heapq.heappush(heap, (h(start_id), 0.0, ctr, start_id))
    ctr += 1
    explored = 0

    while heap:
        f, g, _, cur = heapq.heappop(heap)

        # Lazy deletion — stale entry if we've already found a cheaper g
        if g > g_score.get(cur, math.inf):
            continue

        explored += 1

        if cur == goal_id:
            break

        closed.add(cur)

        for nb, edge_cost, edge_dist, road_name in graph.get(cur, []):
            if nb in closed:
                continue
            tg = g + edge_cost
            if tg < g_score.get(nb, math.inf):
                g_score[nb] = tg
                came_from[nb] = (cur, road_name, edge_dist)
                heapq.heappush(heap, (tg + h(nb), tg, ctr, nb))
                ctr += 1
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
    return path, total_dist, total_time, explored
