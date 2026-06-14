"""Aggregation: sensor-duplicate merge + station -> city (city-median concentrations).

Design decision (see SOURCES.md / Methodology): a city's value for each pollutant is the
**median concentration across its stations** for the period, and AQI is computed from those
city concentrations identically for all three standards. The median (rather than the mean)
is robust to a few stuck or drifting sensors, which would otherwise drag a whole city's value
far above what its typical station reports. AQI is computed from those city concentrations
identically for all three standards, which keeps the standard toggle uniform; it is a
documented deviation from CPCB's exact NAQI city rule (§6, which averages per-station
sub-indices). `n_stations` is retained so NAQI's ">=3 stations" expectation can be surfaced.
"""

from __future__ import annotations

import statistics
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


# Per-pollutant plausibility ceilings (µg/m³; CO mg/m³). Above these is a sensor error, not
# real air — daily means never legitimately reach them. Values are generous so genuine
# extreme-pollution days (e.g. Delhi winter) are kept.
PLAUSIBLE_MAX = {
    "pm25": 1000.0, "pm10": 3000.0, "no2": 1000.0, "so2": 2000.0,
    "o3": 1000.0, "co": 60.0, "nh3": 2000.0,
}

# Recurring device error / saturation codes. These sit below PLAUSIBLE_MAX but are not real
# air: the value 985.0 alone appears hundreds of times across unrelated cities (e.g. the same
# 985.0 reported simultaneously for PM2.5 and PM10), which physical pollution never produces.
# Dropped on any pollutant. Compared with a small tolerance to absorb float noise.
SENSOR_SENTINELS = (985.0, 986.0, 990.0, 991.0, 994.0, 995.0, 1000.0)


def _is_sentinel(value: float) -> bool:
    return any(abs(value - s) < 0.05 for s in SENSOR_SENTINELS)


def drop_implausible(records: list[AQRecord]) -> list[AQRecord]:
    """Remove physically impossible readings: out-of-range values, known sensor sentinel
    codes, and PM2.5 that exceeds PM10 at the same station+time (PM2.5 is a subset of PM10,
    so it cannot be larger)."""
    bounded = [
        r for r in records
        if r.value is not None
        and 0 <= r.value <= PLAUSIBLE_MAX.get(r.parameter, float("inf"))
        and not _is_sentinel(r.value)
    ]
    pm10 = {(r.station_id, r.datetime_utc): r.value
            for r in bounded if r.parameter == "pm10" and r.value is not None}
    out = []
    for r in bounded:
        if r.parameter == "pm25":
            ceiling = pm10.get((r.station_id, r.datetime_utc))
            if ceiling is not None and r.value > ceiling:
                continue  # impossible: PM2.5 > PM10
        out.append(r)
    return out


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
    merged = drop_implausible(merge_sensor_duplicates(records))

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
            # Median (not mean) across stations: a few stuck/drifting sensors must not drag
            # the whole-city value. PM2.5 and PM10 are reported by different station subsets,
            # so the city is best summarized by its typical station, not its average.
            value=statistics.median(values), unit=rs[0].unit,
            n_stations=len({r.station_id for r in rs}),
            coverage_pct=(sum(covs) / len(covs)) if covs else None,
            source=rs[0].source,
        ))
    return _drop_city_pm25_over_pm10(out)


def _drop_city_pm25_over_pm10(
    records: list[CityPollutantRecord],
) -> list[CityPollutantRecord]:
    """Final guard: even after per-station filtering and median aggregation, a city's PM2.5
    can exceed its PM10 when the two pollutants come from different station subsets. PM2.5 is
    a subset of PM10, so that city-day's PM2.5 is untrustworthy -> drop it (AQI then falls
    back to PM10/other), never publishing a spuriously high PM2.5 as the dominant pollutant."""
    pm10 = {(r.city, r.datetime_utc, r.averaging): r.value
            for r in records if r.parameter == "pm10"}
    out = []
    for r in records:
        if r.parameter == "pm25":
            ceiling = pm10.get((r.city, r.datetime_utc, r.averaging))
            if ceiling is not None and r.value > ceiling:
                continue
        out.append(r)
    return out
