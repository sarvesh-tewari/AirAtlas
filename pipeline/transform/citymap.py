"""Derive a station -> city map from CPCB-style station names.

CPCB station names follow one of two conventions:
  - "<Area>, <City> - <Board>"   e.g. "R K Puram, Delhi - DPCC"
  - "<Area> - <City> - <Board>"  e.g. "Collectorate - Gaya - BSPCB"

The parser handles both (~96% of live stations). Names that don't parse are reported as
`unmapped` so they can be added to a manual overrides file (data/meta/station_city_overrides.json).
A city alias map normalizes labels (e.g. "New Delhi" -> "Delhi") — empty by default so we
present cities exactly as CPCB labels them unless explicitly aliased.
"""

from __future__ import annotations

from ingest.records import Station


def city_from_station_name(name: str | None) -> str | None:
    if not name:
        return None
    parts = [p.strip() for p in name.split(" - ")]
    if len(parts) >= 3:
        # "<Area> - <City> - <Board>" -> city is second-to-last.
        return parts[-2] or None
    # Otherwise drop a trailing "- <Board>" and take the last comma-separated chunk.
    head = parts[0]
    chunks = [c.strip() for c in head.split(",")]
    return chunks[-1] if len(chunks) >= 2 and chunks[-1] else None


def build_station_city_map(
    stations: list[Station],
    *,
    overrides: dict[str, str] | None = None,
    aliases: dict[str, str] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Return (station_id -> city, [unmapped station_ids]).

    Resolution order per station: manual override > parsed-from-name. The resulting city
    is then normalized through `aliases`.
    """
    overrides = overrides or {}
    aliases = aliases or {}
    mapping: dict[str, str] = {}
    unmapped: list[str] = []

    for s in stations:
        city = overrides.get(s.station_id) or city_from_station_name(s.name)
        if not city:
            unmapped.append(s.station_id)
            continue
        mapping[s.station_id] = aliases.get(city, city)
    return mapping, unmapped
