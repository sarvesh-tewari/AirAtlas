"""Assemble storage-ready records and write the published data files.

Output shape (the data contract the frontend reads):
  - data/history/<city>.parquet : one row per city per DAY — city-mean concentrations,
    precomputed AQI for all three standards (via the tested Python engine), daily weather,
    source tag, n_stations.
  - data/recent/<city>.parquet  : one row per city per HOUR (last ~90 days) — concentrations
    + hourly weather (no per-hour AQI; AQI needs a 24h window).
  - data/live/<city>.json       : today's snapshot — concentrations, per-pollutant sub-index,
    AQI for all three standards, current weather, source + updated timestamp.

AQI is precomputed here (not in the browser) so there is a single, unit-tested engine.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from aqi import breakpoints as bp, compute
from ingest.records import WeatherRecord
from .aggregate import CityPollutantRecord

POLLUTANTS = ["pm25", "pm10", "no2", "so2", "o3", "co", "nh3"]


def slug(city: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")


def _aqi_block(conc: dict[str, float]) -> dict:
    """Compute all three standards from a city's concentrations."""
    naqi = compute.overall("naqi", conc)
    us = compute.overall("us", conc)
    eu = compute.overall("eu", conc)
    return {
        "aqi_naqi": naqi.index if naqi.valid else None,
        "naqi_category": naqi.category if naqi.valid else None,
        "naqi_dominant": ",".join(naqi.dominant) if naqi.valid else None,
        "aqi_us": us.index if us.valid else None,
        "us_category": us.category if us.valid else None,
        "us_dominant": ",".join(us.dominant) if us.valid else None,
        "eu_band": eu.band if eu.valid else None,
        "eu_dominant": ",".join(eu.dominant) if eu.valid else None,
    }


def _group_by_city_date(records: list[CityPollutantRecord]) -> dict[tuple, list[CityPollutantRecord]]:
    groups: dict[tuple, list[CityPollutantRecord]] = defaultdict(list)
    for r in records:
        groups[(r.city, r.datetime_utc[:10])].append(r)
    return groups


def assemble_daily_rows(
    records: list[CityPollutantRecord],
    weather_by_city_date: dict[tuple, WeatherRecord] | None = None,
) -> list[dict]:
    """Pivot city daily concentration records to wide rows + precomputed AQI + weather."""
    weather_by_city_date = weather_by_city_date or {}
    rows: list[dict] = []
    for (city, date), recs in _group_by_city_date(records).items():
        conc = {r.parameter: r.value for r in recs if r.parameter in POLLUTANTS}
        row: dict = {
            "city": city, "date": date,
            "source": recs[0].source,
            "n_stations": max(r.n_stations for r in recs),
        }
        for p in POLLUTANTS:
            row[p] = conc.get(p)
        row.update(_aqi_block(conc))

        w = weather_by_city_date.get((city, date))
        row.update({
            "temp_c": w.temp_c if w else None,
            "temp_min_c": w.temp_min_c if w else None,
            "temp_max_c": w.temp_max_c if w else None,
            "rh_pct": w.rh_pct if w else None,
            "precip_mm": w.precip_mm if w else None,
            "wind_ms": w.wind_speed_ms if w else None,
        })
        rows.append(row)

    rows.sort(key=lambda r: (r["city"], r["date"]))
    return rows


def assemble_hourly_rows(
    records: list[CityPollutantRecord],
    weather_by_city_hour: dict[tuple, WeatherRecord] | None = None,
) -> list[dict]:
    """Wide hourly rows (concentrations + hourly weather), keyed by full UTC instant."""
    weather_by_city_hour = weather_by_city_hour or {}
    groups: dict[tuple, list[CityPollutantRecord]] = defaultdict(list)
    for r in records:
        groups[(r.city, r.datetime_utc)].append(r)

    rows: list[dict] = []
    for (city, dt), recs in groups.items():
        conc = {r.parameter: r.value for r in recs if r.parameter in POLLUTANTS}
        row: dict = {"city": city, "datetime_utc": dt, "source": recs[0].source}
        for p in POLLUTANTS:
            row[p] = conc.get(p)
        w = weather_by_city_hour.get((city, dt))
        row.update({
            "temp_c": w.temp_c if w else None, "rh_pct": w.rh_pct if w else None,
            "precip_mm": w.precip_mm if w else None,
            "wind_ms": w.wind_speed_ms if w else None,
        })
        rows.append(row)
    rows.sort(key=lambda r: (r["city"], r["datetime_utc"]))
    return rows


def live_snapshot(
    city: str, records: list[CityPollutantRecord], *, updated_utc: str,
    weather: WeatherRecord | None = None,
) -> dict:
    """Today's snapshot for one city."""
    conc = {r.parameter: r.value for r in records if r.parameter in POLLUTANTS}
    units = {r.parameter: r.unit for r in records}

    pollutants = {}
    for p, v in conc.items():
        # Only standards that actually define this pollutant get a sub-index (e.g. NH3 has
        # no US table — computing it would raise). Absent → null.
        pollutants[p] = {
            "value": v,
            "unit": units.get(p, "µg/m³"),
            "naqi_subindex": compute.sub_index("naqi", p, v) if p in bp.NAQI else None,
            "us_subindex": compute.sub_index("us", p, v) if p in bp.US else None,
        }

    naqi, us, eu = (compute.overall(s, conc) for s in ("naqi", "us", "eu"))
    return {
        "city": city,
        "updated_utc": updated_utc,
        "source": records[0].source if records else None,
        "n_stations": max((r.n_stations for r in records), default=0),
        "pollutants": pollutants,
        "aqi": {
            "naqi": {"index": naqi.index, "category": naqi.category,
                     "dominant": naqi.dominant, "valid": naqi.valid},
            "us": {"index": us.index, "category": us.category,
                   "dominant": us.dominant, "valid": us.valid},
            "eu": {"band": eu.band, "category": eu.category, "dominant": eu.dominant,
                   "valid": eu.valid},
        },
        "weather": None if weather is None else {
            "temp_c": weather.temp_c, "rh_pct": weather.rh_pct,
            "precip_mm": weather.precip_mm, "wind_ms": weather.wind_speed_ms,
            "wind_dir_deg": weather.wind_dir_deg,
        },
    }


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #
def write_parquet_per_city(
    rows: list[dict], out_dir: Path, *, city_key: str = "city",
    merge_keys: list[str] | None = None, keep_days: int | None = None,
    date_col: str | None = None,
) -> list[str]:
    """Write one Parquet file per city. Returns the slugs written.

    If `merge_keys` is given and a city's file already exists, new rows are upserted into
    it (existing rows with the same key are replaced) — making refreshes idempotent and
    self-healing. If `keep_days`/`date_col` are given, rows older than that window are pruned
    (used to bound the recent-hourly tier).
    """
    import datetime as _dt

    import polars as pl
    out_dir.mkdir(parents=True, exist_ok=True)
    by_city: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_city[r[city_key]].append(r)

    written = []
    for city, city_rows in by_city.items():
        path = out_dir / f"{slug(city)}.parquet"
        # infer_schema_length=None scans all rows, so a column that's null for the first
        # 100 rows then has a float later won't break type inference.
        df = pl.DataFrame(city_rows, infer_schema_length=None)
        if merge_keys and path.exists():
            existing = pl.read_parquet(path)
            # New rows last so unique(keep="last") lets the delta win on conflicts.
            df = pl.concat([existing, df], how="diagonal_relaxed").unique(
                subset=merge_keys, keep="last", maintain_order=True)
        if keep_days and date_col:
            cutoff = (_dt.date.today() - _dt.timedelta(days=keep_days)).isoformat()
            df = df.filter(pl.col(date_col).str.slice(0, 10) >= cutoff)
        if merge_keys:
            df = df.sort(merge_keys)
        df.write_parquet(path)
        written.append(slug(city))
    return written


def read_all_daily(history_dir: Path) -> list[dict]:
    """Read every per-city daily Parquet back into row dicts — the full published tier.

    Meta (city_list/coverage/cities) is rebuilt from this union so an incremental/subset run
    reflects ALL cities on disk, not just the cities it processed.
    """
    import polars as pl
    rows: list[dict] = []
    for path in sorted(Path(history_dir).glob("*.parquet")):
        rows.extend(pl.read_parquet(path).to_dicts())
    return rows


def drop_sentinel_rows(df):
    """Drop rows carrying a device sentinel/saturation code (e.g. 985.0) on any pollutant.

    A one-time cleanup for already-published parquet: the per-station filter and median
    aggregation prevent these going forward, but rows written before the fix persist because
    an upsert re-fetch produces no replacement row for an all-sentinel station-day."""
    import polars as pl
    from .aggregate import SENSOR_SENTINELS

    present = [c for c in POLLUTANTS if c in df.columns]
    if not present:
        return df
    mask = pl.lit(False)
    for col in present:
        for s in SENSOR_SENTINELS:
            mask = mask | ((pl.col(col) - s).abs() < 0.05).fill_null(False)
    return df.filter(~mask)


def scrub_sentinel_parquets(directory: Path) -> dict:
    """Scrub sentinel rows from every per-city Parquet in `directory`. Files left with no rows
    are deleted (their whole city was a single broken sensor). Returns a summary."""
    import polars as pl
    directory = Path(directory)
    rows_dropped = files_deleted = files_rewritten = 0
    for path in sorted(directory.glob("*.parquet")):
        df = pl.read_parquet(path)
        clean = drop_sentinel_rows(df)
        dropped = df.height - clean.height
        if dropped == 0:
            continue
        rows_dropped += dropped
        if clean.height == 0:
            path.unlink()
            files_deleted += 1
        else:
            clean.write_parquet(path)
            files_rewritten += 1
    return {"rows_dropped": rows_dropped, "files_deleted": files_deleted,
            "files_rewritten": files_rewritten}


def write_live_json(snapshot: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug(snapshot['city'])}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return path


def write_json(obj, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return path
