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

The stargate data comes from django-eveonline-sde (eve_sde). The SDE
must be loaded once for this to work (see README, esde_load_sde).
"""

import heapq
from collections import defaultdict

from django.core.cache import cache

from eve_sde.models import SolarSystem, Stargate

from . import app_settings
from .models import DrifterWormhole, JumpBridge, WormholeStatusReport

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
    pairs = Stargate.objects.values_list(
        "solar_system_id",
        "destination_id",
    )
    for system_id, destination_id in pairs:
        if system_id and destination_id:
            graph[system_id].add(destination_id)
            graph[destination_id].add(system_id)

    graph = dict(graph)
    cache.set(GRAPH_CACHE_KEY, graph, app_settings.SWIFTDRIFT_GRAPH_CACHE_SECONDS)
    return graph


def get_wormhole_edges(
    exclude_ids=None, include_drifters=True, include_normal=True
) -> dict:
    """
    Build the wormhole edges from the currently active entries.

    Returns: {(system_a_id, system_b_id): edge_info, ...} where
    edge_info = {"hive": hive value, "enter": entry-side wormhole,
    "exit": exit-side wormhole}. Directions are stored separately so
    the enter/exit objects are always correct for the travel direction.

    Two edge types:
    - Drifter wormholes: all systems with an active hole of the SAME
      hive are connected to each other (through the hive network).
    - Normal wormholes: a single direct connection between the entry
      system and the reported destination system.

    exclude_ids: wormhole entry ids whose edges are skipped, used by
    the "find alternative route" feature.
    """
    exclude = set(exclude_ids or ())
    edges = {}

    # One wormhole object per (system, hive); newest entry wins
    holes = {}
    normals = []
    for wh in DrifterWormhole.active().order_by("created_at"):
        if wh.id in exclude:
            continue
        if wh.hive == DrifterWormhole.Hive.NORMAL:
            if include_normal and wh.destination_system_id:
                normals.append(wh)
        elif include_drifters:
            holes[(wh.system_id, wh.hive)] = wh

    # Drifter network: connect every pair within the same hive
    by_hive = defaultdict(list)
    for (system_id, hive), wh in holes.items():
        by_hive[hive].append(wh)
    for hive, hive_holes in by_hive.items():
        for i, a in enumerate(hive_holes):
            for b in hive_holes[i + 1 :]:
                edges[(a.system_id, b.system_id)] = {
                    "hive": hive, "enter": a, "exit": b,
                }
                edges[(b.system_id, a.system_id)] = {
                    "hive": hive, "enter": b, "exit": a,
                }

    # Normal wormholes: direct A <-> B, one entry describes both sides
    for wh in normals:
        edges[(wh.system_id, wh.destination_system_id)] = {
            "hive": wh.hive, "enter": wh, "exit": wh,
        }
        edges[(wh.destination_system_id, wh.system_id)] = {
            "hive": wh.hive, "enter": wh, "exit": wh,
        }
    return edges


def find_route(
    start_id: int,
    dest_id: int,
    use_drifters: bool = True,
    use_bridges: bool = True,
    use_normal: bool = True,
    exclude_wormhole_ids=None,
):
    """
    Calculate the shortest route from start_id to dest_id.

    Returns: a list of steps, or None if no route exists.
    Each step is a dict:
        {"system": SolarSystem,
         "via": "start" | "gate" | "drifter" | "bridge",
         "hive": None | "conflux" | ...,          (drifter steps)
         "bridge_name": None | "structure name"}  (bridge steps)
    """
    gates = get_stargate_graph()
    wormhole_edges = {}
    if use_drifters or use_normal:
        wormhole_edges = get_wormhole_edges(
            exclude_wormhole_ids,
            include_drifters=use_drifters,
            include_normal=use_normal,
        )
    wh_weight = app_settings.SWIFTDRIFT_ROUTE_WH_WEIGHT

    # Prepare wormhole neighbors per system
    drifter_neighbors = defaultdict(list)
    for (a, b), edge_info in wormhole_edges.items():
        drifter_neighbors[a].append((b, edge_info))

    # Jump bridges: one row = bidirectional connection, costs 1 like a gate
    bridge_neighbors = defaultdict(list)
    if use_bridges:
        for bridge in JumpBridge.objects.all():
            bridge_neighbors[bridge.from_system_id].append(
                (bridge.to_system_id, bridge.structure_name)
            )
            bridge_neighbors[bridge.to_system_id].append(
                (bridge.from_system_id, bridge.structure_name)
            )

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

        # Wormhole neighbors (drifter network or normal wormholes)
        for neighbor, edge_info in drifter_neighbors.get(current, ()):
            new_dist = dist + wh_weight
            if new_dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_dist
                previous[neighbor] = (current, "drifter", edge_info)
                heapq.heappush(queue, (new_dist, neighbor))

        # Jump bridge neighbors (same cost as a gate jump)
        for neighbor, bridge_name in bridge_neighbors.get(current, ()):
            new_dist = dist + 1
            if new_dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_dist
                previous[neighbor] = (current, "bridge", bridge_name)
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
    systems = SolarSystem.objects.in_bulk(system_ids)

    steps = []
    for system_id, via, extra in path:
        # Display label: normal wormholes read "Wormhole" instead of a
        # hive name ("Exit Wormhole" / "Enter Wormhole here")
        hive_label = None
        if via == "drifter":
            hive_label = (
                "wormhole"
                if extra["hive"] == DrifterWormhole.Hive.NORMAL
                else extra["hive"]
            )
        steps.append(
            {
                "system": systems[system_id],
                "via": via,
                "hive": hive_label,
                "edge": extra if via == "drifter" else None,
                "bridge_name": extra if via == "bridge" else None,
            }
        )

    # ------------------------------------------------------------------
    # Annotate drifter transitions so the pilot knows WHERE to jump in.
    # The step with via="drifter" is the ARRIVAL system; the entry hole
    # is located in the PREVIOUS system. We attach the hive and the
    # in-game bookmark name of the entry and exit wormholes.
    # ------------------------------------------------------------------
    if wormhole_edges:
        for index, step in enumerate(steps):
            if step["via"] != "drifter" or index == 0:
                continue
            edge = step["edge"]
            entry_step = steps[index - 1]
            # Tell the previous step that the pilot enters the hole here
            entry_step["enter_hive"] = step["hive"]
            entry_step["enter_bookmark"] = edge["enter"].bookmark
            entry_step["enter_status"] = _status_of(edge["enter"])
            # Exit side in the arrival system
            step["exit_bookmark"] = edge["exit"].bookmark
            step["exit_status"] = _status_of(edge["exit"])

        _attach_vote_counts(steps)

    return steps


def _status_of(wormhole) -> dict:
    """Status snapshot of a wormhole entry for the route display."""
    return {
        "id": wormhole.id,
        "percent": wormhole.freshness_percent,
        "eol": wormhole.eol,
        "size": wormhole.size.upper() if wormhole.size else "",
        "up": 0,
        "down": 0,
    }


def _attach_vote_counts(steps) -> None:
    """
    Fill in the pilot vote counts for all wormholes used in the route,
    with a single query for the whole route. Counts cover the entire
    lifetime of the entry: votes are one per user (changeable) and are
    deleted together with the wormhole, so they represent the current
    standing opinions.
    """
    status_dicts = {}
    for step in steps:
        for key in ("enter_status", "exit_status"):
            status = step.get(key)
            if status:
                status_dicts.setdefault(status["id"], []).append(status)
    if not status_dicts:
        return

    votes = WormholeStatusReport.objects.filter(
        wormhole_id__in=status_dicts.keys()
    ).values_list("wormhole_id", "is_up")
    for wormhole_id, is_up in votes:
        for status in status_dicts[wormhole_id]:
            status["up" if is_up else "down"] += 1
