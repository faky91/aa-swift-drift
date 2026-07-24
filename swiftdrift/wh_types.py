"""
Static wormhole type catalog.

Source: EVE University Wiki, "Wormhole attributes"
(https://wiki.eveuniversity.org/Wormhole_attributes, CC BY-SA 4.0),
last cross-checked 2026-07 against ellatha.com/eve/wormholelist.asp.
Where the two sources disagree on lifetimes (e.g. C248, E545, K329,
V283, C391, B520, C729), the EVE Uni values were used because that
page is actively maintained and reflects recent balance changes.

Entry format per type code:
    (goes_from, leads_to, total_mass_t, max_ship_mass_t,
     mass_regen_t_per_day, max_stable_hours)

Masses are in tons (t = 1000 kg), matching the in-game show-info.
K162 is the generic exit side and has no own attributes.
"""

WH_TYPES = {
    "A009": ("", "C13", 500_000, 5_000, 0, 4.5),
    "A239": ("C2", "Lowsec", 2_000_000, 375_000, 0, 24),
    "A641": ("Highsec", "Highsec", 2_000_000, 1_000_000, 0, 16),
    "A982": ("C3", "C6", 3_000_000, 375_000, 0, 24),
    "B041": ("Highsec", "C6", 5_000_000, 375_000, 500_000, 48),
    "B274": ("C2", "Highsec", 2_000_000, 375_000, 0, 24),
    "B449": ("Lowsec/Nullsec", "Highsec", 2_000_000, 1_000_000, 0, 16),
    "B520": ("C6", "Highsec", 5_000_000, 375_000, 500_000, 24),
    "B735": ("", "Drifter Barbican", 750_000, 375_000, 0, 16),
    "C008": ("", "C5", 1_000_000, 5_000, 500_000, 4.5),
    "C125": ("C1", "C2", 1_000_000, 62_000, 0, 16),
    "C140": ("C5/C6", "Lowsec", 3_300_000, 2_000_000, 0, 24),
    "C247": ("C4", "C3", 2_000_000, 375_000, 0, 16),
    "C248": ("C6", "Nullsec", 3_300_000, 2_000_000, 500_000, 24),
    "C391": ("C6", "Lowsec", 5_000_000, 2_000_000, 500_000, 24),
    "C414": ("", "Drifter Conflux", 750_000, 375_000, 0, 16),
    "C729": ("adjacent systems", "Pochven", 1_000_000, 375_000, 0, 16),
    "D364": ("C5", "C2", 1_000_000, 375_000, 0, 16),
    "D382": ("C2", "C2", 2_000_000, 375_000, 0, 16),
    "D792": ("C5", "Highsec", 3_000_000, 1_000_000, 0, 24),
    "D845": ("C3", "Highsec", 5_000_000, 375_000, 500_000, 24),
    "E004": ("", "C1", 1_000_000, 5_000, 500_000, 4.5),
    "E175": ("C5", "C4", 2_000_000, 375_000, 0, 16),
    "E545": ("C2", "Nullsec", 2_000_000, 375_000, 0, 24),
    "E587": ("Thera", "Nullsec", 3_000_000, 1_000_000, 0, 16),
    "F135": ("C2/C3", "Thera", 750_000, 375_000, 0, 16),
    "F216": ("C2-C6", "Pochven", 1_000_000, 375_000, 0, 16),
    "F353": ("C1", "Thera", 100_000, 62_000, 0, 16),
    "G008": ("", "C6", 1_000_000, 5_000, 500_000, 4.5),
    "G024": ("C6", "C2", 2_000_000, 375_000, 0, 16),
    "H121": ("C1", "C1", 500_000, 62_000, 0, 16),
    "H296": ("C5", "C5", 3_300_000, 2_000_000, 0, 24),
    "H900": ("C4", "C5", 3_000_000, 375_000, 0, 24),
    "I182": ("C3", "C2", 2_000_000, 375_000, 0, 16),
    "J244": ("C1", "Lowsec", 1_000_000, 62_000, 0, 24),
    "J377": ("C1-C4", "Turnur", 1_000_000, 62_000, 0, 24),
    "K162": ("", "Generic exit", None, None, None, None),
    "K329": ("C4", "Nullsec", 3_000_000, 375_000, 0, 24),
    "K346": ("C3", "Nullsec", 3_000_000, 375_000, 0, 24),
    "L005": ("", "C2", 1_000_000, 5_000, 500_000, 4.5),
    "L031": ("Nullsec", "Thera", 3_000_000, 1_000_000, 0, 16),
    "L477": ("C6", "C3", 2_000_000, 375_000, 0, 16),
    "L614": ("C1", "C5", 1_000_000, 62_000, 0, 24),
    "M001": ("", "C4", 1_000_000, 5_000, 500_000, 4.5),
    "M164": ("Lowsec", "Thera", 2_000_000, 375_000, 0, 16),
    "M267": ("C5", "C3", 1_000_000, 375_000, 0, 16),
    "M555": ("Highsec", "C5", 3_000_000, 1_000_000, 0, 24),
    "M609": ("C1", "C4", 1_000_000, 62_000, 0, 16),
    "N062": ("C2", "C5", 3_000_000, 375_000, 0, 24),
    "N110": ("C1", "Highsec", 1_000_000, 62_000, 0, 24),
    "N290": ("C4", "Lowsec", 3_000_000, 375_000, 0, 24),
    "N432": ("Lowsec/Nullsec", "C5", 3_300_000, 2_000_000, 0, 24),
    "N766": ("C4", "C2", 2_000_000, 375_000, 0, 16),
    "N770": ("C3", "C5", 3_000_000, 375_000, 0, 24),
    "N944": ("Lowsec/Nullsec", "Lowsec", 3_300_000, 2_000_000, 0, 24),
    "N968": ("C3", "C3", 2_000_000, 375_000, 0, 16),
    "O128": ("K-space", "C4", 1_000_000, 375_000, 100_000, 24),
    "O477": ("C2", "C3", 2_000_000, 375_000, 0, 16),
    "O883": ("C1", "C3", 1_000_000, 62_000, 0, 16),
    "P060": ("C4", "C1", 500_000, 62_000, 0, 16),
    "Q003": ("", "Nullsec", 1_000_000, 5_000, 500_000, 4.5),
    "Q063": ("Thera", "Highsec", 500_000, 62_000, 0, 16),
    "Q317": ("C6", "C1", 500_000, 62_000, 0, 16),
    "R051": ("Highsec", "Lowsec", 3_000_000, 1_000_000, 0, 16),
    "R081": ("Pochven", "C4", 1_000_000, 450_000, 0, 16),
    "R259": ("", "Drifter Redoubt", 750_000, 375_000, 0, 16),
    "R474": ("C2", "C6", 3_000_000, 375_000, 0, 24),
    "R943": ("K-space", "C2", 750_000, 375_000, 0, 16),
    "S047": ("C4", "Highsec", 3_000_000, 375_000, 0, 24),
    "S199": ("Lowsec/Nullsec", "Nullsec", 3_300_000, 2_000_000, 0, 24),
    "S804": ("C1", "C6", 1_000_000, 62_000, 0, 24),
    "S877": ("", "Drifter Sentinel", 750_000, 375_000, 0, 16),
    "T405": ("C3", "C4", 2_000_000, 375_000, 0, 16),
    "T458": ("Highsec", "Thera", 500_000, 62_000, 0, 16),
    "U210": ("C3", "Lowsec", 3_000_000, 375_000, 0, 23.5),
    "U319": ("Lowsec/Nullsec", "C6", 3_300_000, 2_000_000, 500_000, 48),
    "U372": ("Drone Nullsec", "Pochven", 1_000_000, 375_000, 0, 16),
    "U574": ("C4", "C6", 3_000_000, 375_000, 0, 24),
    "V283": ("Highsec", "Nullsec", 3_000_000, 1_000_000, 0, 24),
    "V301": ("C3", "C1", 500_000, 62_000, 0, 16),
    "V753": ("C5", "C6", 3_300_000, 2_000_000, 0, 24),
    "V898": ("Thera", "Lowsec", 2_000_000, 375_000, 0, 16),
    "V911": ("C6", "C5", 3_300_000, 2_000_000, 0, 24),
    "V928": ("", "Drifter Vidette", 750_000, 375_000, 0, 16),
    "W237": ("C6", "C6", 3_300_000, 2_000_000, 0, 24),
    "X450": ("Pochven", "Drone Nullsec", 1_000_000, 375_000, 0, 16),
    "X702": ("K-space", "C3", 1_000_000, 375_000, 0, 24),
    "X877": ("C4", "C4", 2_000_000, 375_000, 0, 16),
    "Y683": ("C2", "C4", 2_000_000, 375_000, 0, 16),
    "Y790": ("C5", "C1", 500_000, 62_000, 0, 16),
    "Z006": ("", "C3", 1_000_000, 5_000, 5_000, 4.5),
    "Z060": ("C1", "Nullsec", 1_000_000, 62_000, 0, 24),
    "Z142": ("C5/C6", "Nullsec", 3_300_000, 2_000_000, 0, 24),
    "Z457": ("C6", "C4", 2_000_000, 375_000, 0, 16),
    "Z647": ("C2", "C1", 500_000, 62_000, 0, 16),
    "Z971": ("K-space", "C1", 100_000, 62_000, 0, 16),
}


def get_type(code: str):
    """Look up a type code case-insensitively. Returns the tuple or None."""
    if not code:
        return None
    return WH_TYPES.get(code.strip().upper())


def size_for(code: str) -> str:
    """
    Derive the ship size letter (s/m/l/xl) from the max individual
    mass, matching the in-game aurora colors:
    5,000 t = frigate/destroyer hole (S), 62,000 t = medium (M),
    up to 450,000 t = large (L), above = capitals (XL).
    """
    entry = get_type(code)
    if not entry or entry[3] is None:
        return ""
    max_ship = entry[3]
    if max_ship <= 5_000:
        return "s"
    if max_ship <= 62_000:
        return "m"
    if max_ship <= 450_000:
        return "l"
    return "xl"


def lifetime_for(code: str):
    """Max stable time in hours, or None (e.g. K162)."""
    entry = get_type(code)
    return entry[5] if entry else None


def summary_for(code: str) -> str:
    """One-line summary, e.g. 'C2 -> Highsec, 24h, L, 2,000,000 t'."""
    entry = get_type(code)
    if not entry:
        return ""
    goes_from, leads_to, total, max_ship, _regen, lifetime = entry
    parts = []
    if goes_from:
        parts.append(f"{goes_from} -> {leads_to}")
    else:
        parts.append(f"-> {leads_to}")
    if lifetime:
        hours = int(lifetime) if float(lifetime).is_integer() else lifetime
        parts.append(f"{hours}h")
    size = size_for(code)
    if size:
        parts.append(size.upper())
    if total:
        parts.append(f"{total:,} t total")
    if max_ship:
        parts.append(f"{max_ship:,} t per ship")
    return ", ".join(parts)


def choices():
    """(code, 'CODE - summary') pairs for autocomplete lists."""
    return [
        (code, f"{code} - {summary_for(code)}")
        for code in sorted(WH_TYPES.keys())
    ]
