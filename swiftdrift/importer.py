"""
Bulk import parser for jump bridge lists.

Accepts one bridge per line and tolerates the common community formats.
The primary format is the corptools export, which starts with the
in-game structure ID (useful for finding the Ansiblex in game):

    1045899402916 Y-2ANO --> KVN-36

Also accepted:

    Y-2ANO --> KVN-36
    Y-2ANO » KVN-36 - Papa Bridge
    Y-2ANO <> KVN-36
    Y-2ANO,KVN-36,optional name
    Y-2ANO;KVN-36

System names may contain spaces (e.g. "Old Man Star"), so the parser
splits on explicit separators only, never on plain whitespace.
"""

from eve_sde.models import SolarSystem

from .forms import KSPACE_MAX_ID, KSPACE_MIN_ID

# Separators between the two system names, tried in this order.
# The Ansiblex separator comes first because it is the corptools format.
SEPARATORS = ["»", "-->", "<->", "<>", "->", ";", ",", "\t"]


def _split_line(line: str):
    """
    Split one line into (structure_id, from_name, to_name, structure_name).
    structure_id is None when the line does not start with one.
    Returns None if no known separator is found.
    """
    # Optional leading structure ID (corptools export format)
    structure_id = None
    first, _, rest = line.partition(" ")
    if first.isdigit() and rest.strip():
        structure_id = int(first)
        line = rest.strip()

    for separator in SEPARATORS:
        if separator in line:
            left, right = line.split(separator, 1)

            # Ansiblex names carry " - Nickname" after the target system
            if " - " in right:
                to_part, _ = right.split(" - ", 1)
            else:
                to_part = right

            # CSV variant may carry the name as a third column instead
            if separator in (",", ";") and separator in to_part:
                to_part = to_part.split(separator, 1)[0]

            return structure_id, left.strip(), to_part.strip(), line.strip()
    return None


def parse_jump_bridges(text: str):
    """
    Parse a pasted bridge list.

    Returns (entries, errors):
    - entries: list of dicts {from_system, to_system, structure_name}
    - errors:  list of strings describing lines that could not be parsed
    """
    # Cache all k-space systems once: name (lowercase) -> object.
    # ~5300 rows, cheaper than one query per line.
    systems = {
        s.name.lower(): s
        for s in SolarSystem.objects.filter(
            id__gte=KSPACE_MIN_ID, id__lt=KSPACE_MAX_ID
        )
    }

    entries = []
    errors = []
    seen_pairs = set()

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue  # empty lines and comments are fine

        parsed = _split_line(line)
        if parsed is None:
            errors.append(f"Line {line_number}: no separator found: {line!r}")
            continue

        structure_id, from_name, to_name, structure_name = parsed
        from_system = systems.get(from_name.lower())
        to_system = systems.get(to_name.lower())

        if from_system is None:
            errors.append(f"Line {line_number}: unknown system {from_name!r}")
            continue
        if to_system is None:
            errors.append(f"Line {line_number}: unknown system {to_name!r}")
            continue
        if from_system.id == to_system.id:
            errors.append(f"Line {line_number}: from and to are identical")
            continue

        # Deduplicate inside the pasted list (both directions)
        pair = tuple(sorted((from_system.id, to_system.id)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        entries.append(
            {
                "structure_id": structure_id,
                "from_system": from_system,
                "to_system": to_system,
                "structure_name": structure_name[:100],
            }
        )

    return entries, errors
