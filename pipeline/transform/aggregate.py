"""Aggregation: sensor-duplicate merge + station -> city (city-mean concentrations).

Design decision (see SOURCES.md / Methodology): a city's value for each pollutant is the
**mean concentration across its stations** for the period, and AQI is computed from those
city concentrations identically for all three standards. This is consistent with the build
plan §8.5 (client-side AQI from 24h-aggregated concentrations) and keeps the standard toggle
uniform; it is a documented, slight deviation from CPCB's exact NAQI city rule (§6, which
averages per-station sub-indices). `n_stations` is retained so NAQI's ">=3 stations"
expectation can be surfaced.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ingest.records import AQRecord


@dataclass
class CityPollutantRecord:
    city: str
    parameter: str
    datetime_utc: str          # day key ("...T00:00:00Z") or hour instant
    averaging: str             # "live" | "1h" | "1d"
    value: float               # city-mean concentration (µg/m³, CO mg/m³)
    unit: str
    n_stations: int
    coverage_pct: float | None
    source: str = ""           # set during reconciliation ("cpcb" | "openaq")


def _cov(r: AQRecord) -> float:
    return r.coverage_pct if r.coverage_pct is not None else -1.0


def merge_sensor_duplicates(records: list[AQRecord]) -> list[AQRecord]:
    """Collapse duplicate sensors: one value per (station, parameter, datetime),
    keeping the record with the highest coverage (ties -> first seen)."""
    best: dict[tuple, AQRecord] = {}
    for r in records:
        key = (r.station_id, r.parameter, r.datetime_utc, r.averaging)
        cur = best.get(key)
        if cur is None or _cov(r) > _cov(cur):
            best[key] = r
    return list(best.values())


def aggregate_to_city(
    records: list[AQRecord],
    station_city: dict[str, str] | None = None,
    *,
    min_coverage: float = 0.0,
) -> list[CityPollutantRecord]:
    """Average each pollutant's concentration across a city's stations, per period.

    City is taken from the record's own `city` (CPCB) or resolved via `station_city`
    (OpenAQ). Station-days below `min_coverage` are dropped before averaging. Duplicate
    sensors are merged first.
    """
    station_city = station_city or {}
    merged = merge_sensor_duplicates(records)

    groups: dict[tuple, list[AQRecord]] = defaultdict(list)
    for r in merged:
        if r.value is None:
            continue
        if r.coverage_pct is not None and r.coverage_pct < min_coverage:
            continue
        city = r.city or station_city.get(r.station_id)
        if not city:
            continue
        groups[(city, r.parameter, r.datetime_utc, r.averaging)].append(r)

    out: list[CityPollutantRecord] = []
    for (city, param, dt, averaging), rs in groups.items():
        values = [r.value for r in rs]
        covs = [r.coverage_pct for r in rs if r.coverage_pct is not None]
        out.append(CityPollutantRecord(
            city=city, parameter=param, datetime_utc=dt, averaging=averaging,
            value=sum(values) / len(values), unit=rs[0].unit,
            n_stations=len({r.station_id for r in rs}),
            coverage_pct=(sum(covs) / len(covs)) if covs else None,
            source=rs[0].source,
        ))
    return out
