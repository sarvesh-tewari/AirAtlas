"""Orchestration helpers: discover stations, fetch each tier, aggregate, and write.

These compose the ingest + transform + storage layers into the actual data build. A full
multi-year, all-city backfill is heavy (hundreds of stations × pollutants × years), so each
function is parameterizable (city subset, date window, per-city station cap) — run.py drives
hourly / daily / backfill modes; CI runs the full thing.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ingest import cpcb, openaq, openmeteo
from ingest.records import AQRecord, Station
from transform import aggregate as agg
from transform import citymap

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
META = DATA / "meta"

AQI_PARAMS = {"pm25", "pm10", "no2", "so2", "o3", "co", "nh3"}


# --------------------------------------------------------------------------- #
# Discovery + mapping
# --------------------------------------------------------------------------- #
def _load_meta_json(name: str, default):
    path = META / name
    if path.exists():
        return json.loads(path.read_text())
    return default


def discover(api_key: str) -> tuple[list[Station], dict[str, str], list[str]]:
    """All CPCB stations + station->city map (with overrides/aliases) + unmapped ids."""
    stations = openaq.fetch_india_locations(api_key, page_size=1000)
    overrides = _load_meta_json("station_city_overrides.json", {})
    aliases = _load_meta_json("city_aliases.json", {})
    mapping, unmapped = citymap.build_station_city_map(
        stations, overrides=overrides, aliases=aliases)
    return stations, mapping, unmapped


def select_stations(stations, mapping, *, cities=None, max_per_city=None):
    """Filter stations to target cities, optionally capping stations per city."""
    chosen, counts = [], defaultdict(int)
    for s in stations:
        city = mapping.get(s.station_id)
        if city is None or (cities and city not in cities):
            continue
        if max_per_city and counts[city] >= max_per_city:
            continue
        counts[city] += 1
        chosen.append(s)
    return chosen


def city_centroids(stations, mapping) -> dict[str, tuple[float, float]]:
    pts: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for s in stations:
        city = mapping.get(s.station_id)
        if city and s.lat is not None and s.lon is not None:
            pts[city].append((s.lat, s.lon))
    return {c: (sum(a for a, _ in v) / len(v), sum(b for _, b in v) / len(v))
            for c, v in pts.items()}


def _sensors_for(station: Station, mode: str):
    """Yield (sensor_id, parameter). mode='first' = one sensor per pollutant; 'all' = every sensor."""
    seen = set()
    for se in station.sensors:
        if se.parameter not in AQI_PARAMS:
            continue
        if mode == "first" and se.parameter in seen:
            continue
        seen.add(se.parameter)
        yield se.sensor_id, se.parameter


# --------------------------------------------------------------------------- #
# Per-tier fetch -> city aggregation
# --------------------------------------------------------------------------- #
def fetch_city_aq(api_key, stations, mapping, *, date_from, date_to, period="days",
                  sensors="first", min_coverage=0.0) -> list[agg.CityPollutantRecord]:
    """Fetch AQ history for the given stations and aggregate to city level."""
    raw: list[AQRecord] = []
    for s in stations:
        city = mapping.get(s.station_id)
        for sensor_id, _param in _sensors_for(s, sensors):
            try:
                raw += openaq.fetch_sensor_history(
                    api_key, sensor_id, date_from=date_from, date_to=date_to, period=period,
                    station_id=s.station_id, station_name=s.name, city=city,
                    state=None, lat=s.lat, lon=s.lon)
            except Exception as e:
                # One flaky sensor must not abort the whole build (self-healing: it backfills
                # on the next run). Log and continue.
                print(f"[build] skip sensor {sensor_id} ({period}) for {city}: {type(e).__name__}",
                      flush=True)
    return agg.aggregate_to_city(raw, mapping, min_coverage=min_coverage)


def fetch_weather_daily(centroids, *, start_date, end_date) -> dict[tuple, object]:
    out = {}
    for city, (lat, lon) in centroids.items():
        try:  # one city's weather failing (e.g. ERA5 lag -> 400) must not abort the run
            for w in openmeteo.fetch_archive_daily(lat, lon, start_date=start_date, end_date=end_date):
                out[(city, w.datetime_utc[:10])] = w
        except Exception as e:
            print(f"[build] skip daily weather for {city}: {type(e).__name__}", flush=True)
    return out


def fetch_weather_current(centroids) -> dict[str, object]:
    out = {}
    for city, (lat, lon) in centroids.items():
        try:
            w = openmeteo.fetch_current(lat, lon)
            if w is not None:
                out[city] = w
        except Exception as e:
            print(f"[build] skip current weather for {city}: {type(e).__name__}", flush=True)
    return out


def fetch_live_cpcb(api_key, mapping) -> list[agg.CityPollutantRecord]:
    """CPCB nationwide live snapshot, aggregated to city (uses CPCB's own city field)."""
    raw = cpcb.fetch_live(api_key)
    return agg.aggregate_to_city(raw, mapping)


# --------------------------------------------------------------------------- #
# Coverage report
# --------------------------------------------------------------------------- #
def build_cities_index(daily_rows, centroids) -> list[dict]:
    """One row per city with centroid + latest-day AQI — powers the map, combobox, compare."""
    by_city: dict[str, list[dict]] = defaultdict(list)
    for r in daily_rows:
        by_city[r["city"]].append(r)
    out = []
    for city, rows in sorted(by_city.items()):
        last = max(rows, key=lambda r: r["date"])
        lat, lon = centroids.get(city, (None, None))
        out.append({
            "city": city, "lat": lat, "lon": lon,
            "last_date": last["date"], "n_stations": last["n_stations"],
            "naqi": last["aqi_naqi"], "naqi_category": last["naqi_category"],
            "us": last["aqi_us"], "us_category": last["us_category"],
            "eu_band": last["eu_band"],
        })
    return out


def merge_centroids(centroids: dict, prior_index: list[dict]) -> dict:
    """Fill centroids for cities this run didn't process from the previously-published index.

    When meta is rebuilt from the full on-disk union, cities outside this batch still need a
    lat/lon for their map marker; recover it from the prior cities.json. This run's freshly
    computed centroids take precedence over the prior (possibly stale) values.
    """
    merged = dict(centroids)
    for e in prior_index:
        if e["city"] not in merged and e.get("lat") is not None:
            merged[e["city"]] = (e["lat"], e["lon"])
    return merged


def build_coverage(daily_rows, *, thin_days=365) -> list[dict]:
    by_city: dict[str, list[dict]] = defaultdict(list)
    for r in daily_rows:
        by_city[r["city"]].append(r)
    report = []
    for city, rows in sorted(by_city.items()):
        dates = sorted(r["date"] for r in rows)
        report.append({
            "city": city, "n_days": len(dates),
            "first_date": dates[0], "last_date": dates[-1],
            "thin": len(dates) < thin_days,
        })
    return report
