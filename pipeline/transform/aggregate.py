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

import datetime as dt
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
    for (city, param, datetime_utc, averaging), rs in groups.items():
        values = [r.value for r in rs]
        covs = [r.coverage_pct for r in rs if r.coverage_pct is not None]
        out.append(CityPollutantRecord(
            city=city, parameter=param, datetime_utc=datetime_utc, averaging=averaging,
            # Median (not mean) across stations: a few stuck/drifting sensors must not drag
            # the whole-city value. PM2.5 and PM10 are reported by different station subsets,
            # so the city is best summarized by its typical station, not its average.
            value=statistics.median(values), unit=rs[0].unit,
            n_stations=len({r.station_id for r in rs}),
            coverage_pct=(sum(covs) / len(covs)) if covs else None,
            source=rs[0].source,
        ))
    return _drop_city_pm25_over_pm10(out)


def rollup_hourly_to_daily(
    hourly: list[CityPollutantRecord], *, min_hours: int = 18, tz_offset_hours: float = 5.5,
) -> list[CityPollutantRecord]:
    """Roll city-hour concentration records up to city-day records by arithmetic MEAN.

    This matches OpenAQ's /days `summary.avg` (the value our historical tier was built on), so
    self-computed days are methodologically identical to the old /days-derived days. Median-across-
    stations is already applied per hour upstream (aggregate_to_city), so this only collapses the
    time axis. A (city, pollutant, local-day) value is emitted ONLY if at least `min_hours` valid
    hours are present; sparser days are omitted, never fabricated. Hours are bucketed by LOCAL
    calendar day (IST, +5:30) to match the daily tier's local-date keying.
    """
    tz = dt.timezone(dt.timedelta(hours=tz_offset_hours))
    groups: dict[tuple, list[CityPollutantRecord]] = defaultdict(list)
    for r in hourly:
        if r.value is None:
            continue
        try:
            ts = dt.datetime.fromisoformat(r.datetime_utc.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        local_date = ts.astimezone(tz).date().isoformat()
        groups[(r.city, r.parameter, local_date)].append(r)

    out: list[CityPollutantRecord] = []
    for (city, param, local_date), rs in groups.items():
        if len(rs) < min_hours:
            continue
        values = [r.value for r in rs]
        covs = [r.coverage_pct for r in rs if r.coverage_pct is not None]
        out.append(CityPollutantRecord(
            city=city, parameter=param, datetime_utc=f"{local_date}T00:00:00Z",
            averaging="1d", value=sum(values) / len(values), unit=rs[0].unit,
            n_stations=max(r.n_stations for r in rs),
            coverage_pct=(sum(covs) / len(covs)) if covs else None,
            source=rs[0].source or "openaq",
        ))
    return out


def rolling_24h(
    hourly: list[CityPollutantRecord], *, min_hours: int = 12, window_hours: int = 24,
) -> list[CityPollutantRecord]:
    """Per-city trailing-window mean from hourly city records, for the live headline.

    For each city, find its most recent available hour, take the window of hours strictly after
    `latest - window_hours` (up to and including the latest hour), and compute the arithmetic
    MEAN per pollutant (same method as the daily rollup and OpenAQ's summary.avg). A pollutant
    is emitted only if it has >= `min_hours` readings in the window. The emitted record's
    datetime_utc is the city's most recent hour, so the live snapshot is stamped with the
    freshest reading time. Median-across-stations is already applied per hour.
    """
    def _ts(r: CityPollutantRecord) -> dt.datetime:
        return dt.datetime.fromisoformat(r.datetime_utc.replace("Z", "+00:00"))

    by_city: dict[str, list[CityPollutantRecord]] = defaultdict(list)
    for r in hourly:
        if r.value is not None:
            by_city[r.city].append(r)

    out: list[CityPollutantRecord] = []
    for city, rows in by_city.items():
        latest_row = max(rows, key=_ts)
        cutoff = _ts(latest_row) - dt.timedelta(hours=window_hours)
        window = [r for r in rows if _ts(r) > cutoff]
        by_param: dict[str, list[CityPollutantRecord]] = defaultdict(list)
        for r in window:
            by_param[r.parameter].append(r)
        for param, rs in by_param.items():
            if len(rs) < min_hours:
                continue
            values = [r.value for r in rs]
            covs = [r.coverage_pct for r in rs if r.coverage_pct is not None]
            out.append(CityPollutantRecord(
                city=city, parameter=param, datetime_utc=latest_row.datetime_utc,
                averaging="24h", value=sum(values) / len(values), unit=rs[0].unit,
                n_stations=max(r.n_stations for r in rs),
                # Always openaq: this is the OpenAQ-hourly rolling path by construction; CPCB has
                # its own real-time live path. The frontend keys rolling-24h treatment on this.
                coverage_pct=(sum(covs) / len(covs)) if covs else None, source="openaq",
            ))
    return out


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
