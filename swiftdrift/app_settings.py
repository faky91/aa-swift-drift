"""
App settings with sensible defaults.

Every value can be overridden in the local.py of the Auth installation,
for example:

    SWIFTDRIFT_DEFAULT_LIFETIME_HOURS = 12
"""

from django.conf import settings


def _get(name: str, default):
    """Read a setting from local.py or fall back to the default."""
    return getattr(settings, name, default)


# Maximum lifetime of a wormhole entry in hours (counted from creation).
# Drifter wormholes typically live for about 16 hours.
SWIFTDRIFT_DEFAULT_LIFETIME_HOURS: int = _get("SWIFTDRIFT_DEFAULT_LIFETIME_HOURS", 16)

# Remaining lifetime in hours once a wormhole is flagged as "End of Life".
# In EVE, EOL means less than 4 hours remaining.
SWIFTDRIFT_EOL_LIFETIME_HOURS: int = _get("SWIFTDRIFT_EOL_LIFETIME_HOURS", 4)

# "Cost" of a drifter jump in the route planner, measured in gate jumps.
# 2 = one jump into the hive, one jump out. Lower it to 1 if you want the
# planner to prefer drifter shortcuts more aggressively.
SWIFTDRIFT_ROUTE_WH_WEIGHT: int = _get("SWIFTDRIFT_ROUTE_WH_WEIGHT", 2)

# How long the stargate graph is kept in the cache (seconds).
# Stargate data practically never changes, so 24h is safe.
SWIFTDRIFT_GRAPH_CACHE_SECONDS: int = _get("SWIFTDRIFT_GRAPH_CACHE_SECONDS", 86400)
