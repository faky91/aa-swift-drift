"""
Route calculation.

Basic idea:
- The regular EVE map is a graph: systems = nodes, stargates = edges.
- Active drifter wormholes add extra edges: all systems with an active
  wormhole to the SAME hive are connected to each other (jump into
  hive X in system A, jump out of hive X in system B).
- On top of that runs a Dijkstra algorithm (shortest path with weights),
  implemented with Python standard library only (heapq), no external
  dependency.

The stargate data comes from django-eveuniverse. The map including
stargates must be loaded for this to work (see README,
EVEUNIVERSE_LOAD_STARGATES).
"""

import heapq
from collections import defaultdict

from django.core.cache import cache

from eveuniverse.models import EveSolarSystem, EveStargate

from . import app_settings
from .models import DrifterWormhole

# Cache key for the stargate graph
GRAPH_CACHE_KEY = "swiftdrift_stargate_graph"


def get_stargate_graph() -> dict:
    """
    Build the stargate adjacency list: {system_id: {neighbor_ids}}.

    The result is cached because stargates practically never change and
    the query would otherwise cost unnecessary time with ~5000 systems.
    """
    graph = cache.get(GRAPH_CACHE_KEY)
    if graph is not None:
        return graph

    graph = defaultdict(set)
    # Every stargate knows its own system and the destination system
    pairs = EveStargate.objects.values_list(
        "eve_solar_system_id",
        "destination_eve_solar_system_id",
    )
    for system_id, destination_id in pairs:
        if system_id and destination_id:
            graph[system_id].add(destination_id)
            graph[destination_id].add(system_id)

    graph = dict(graph)
    cache.set(GRAPH_CACHE_KEY, graph, app_settings.SWIFTDRIFT_GRAPH_CACHE_SECONDS)
    return graph


def get_drifter_edges() -> dict:
    """
    Build the drifter edges from the currently active wormholes.

    Returns: {(system_a_id, system_b_id): hive_name, ...}
    for all system pairs connected through the same hive.
    """
    # Group active wormholes by hive
    by_hive = defaultdict(set)
    for wh in DrifterWormhole.active().select_related("system"):
        by_hive[wh.hive].add(wh.system_id)

    edges = {}
    for hive, system_ids in by_hive.items():
        ids = sorted(system_ids)
        # Connect every pair within the same hive
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                edges[(a, b)] = hive
                edges[(b, a)] = hive
    return edges


def find_route(start_id: int, dest_id: int, use_swiftdrift: bool = True):
    """
    Calculate the shortest route from start_id to dest_id.

    Returns: a list of steps, or None if no route exists.
    Each step is a dict:
        {"system": EveSolarSystem, "via": "start" | "gate" | "drifter",
         "hive": None | "conflux" | ...}
    """
    gates = get_stargate_graph()
    drifter_edges = get_drifter_edges() if use_drifters else {}
    wh_weight = app_settings.SWIFTDRIFT_ROUTE_WH_WEIGHT

    # Prepare drifter neighbors per system
    drifter_neighbors = defaultdict(list)
    for (a, b), hive in drifter_edges.items():
        drifter_neighbors[a].append((b, hive))

    # ------------------------------------------------------------------
    # Dijkstra: shortest path with edge weights.
    # Gate jump = 1, drifter jump = wh_weight (default: 2)
    # ------------------------------------------------------------------
    distances = {start_id: 0}
    # previous stores per system: (predecessor, jump type, hive)
    previous = {}
    queue = [(0, start_id)]
    visited = set()

    while queue:
        dist, current = heapq.heappop(queue)
        if current in visited:
            continue
        visited.add(current)

        if current == dest_id:
            break  # destination reached

        # Regular stargate neighbors
        for neighbor in gates.get(current, ()):
            new_dist = dist + 1
            if new_dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_dist
                previous[neighbor] = (current, "gate", None)
                heapq.heappush(queue, (new_dist, neighbor))

        # Drifter neighbors (same hive)
        for neighbor, hive in drifter_neighbors.get(current, ()):
            new_dist = dist + wh_weight
            if new_dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_dist
                previous[neighbor] = (current, "drifter", hive)
                heapq.heappush(queue, (new_dist, neighbor))

    if dest_id not in previous and start_id != dest_id:
        return None  # no route found

    # ------------------------------------------------------------------
    # Reconstruct the path backwards
    # ------------------------------------------------------------------
    path = []
    node = dest_id
    while node != start_id:
        prev_node, via, hive = previous[node]
        path.append((node, via, hive))
        node = prev_node
    path.append((start_id, "start", None))
    path.reverse()

    # Load all system objects in one query (instead of one per step)
    system_ids = [system_id for system_id, _, _ in path]
    systems = EveSolarSystem.objects.in_bulk(system_ids)

    return [
        {"system": systems[system_id], "via": via, "hive": hive}
        for system_id, via, hive in path
    ]
