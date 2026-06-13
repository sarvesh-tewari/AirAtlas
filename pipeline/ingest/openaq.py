"""OpenAQ history fetch (API v3) + parsing.

OpenAQ re-ingests CPCB's Indian stations and keeps multi-year history with ready
daily/hourly aggregations. We read OPENAQ_API_KEY from the environment.

Key shape facts (verified against the live v3 API):
  - A location has many `sensors`; each sensor is one parameter, with its own units
    (gases are often ppb; PM is µg/m³). A station's multi-year series for one pollutant
    can be SPLIT across several sensor ids over time, so callers union all same-parameter
    sensors at a location.
  - Aggregate endpoints (/sensors/{id}/days, /hours) return per-period records with a
    `summary` (avg/min/max/…) and `coverage.percentComplete`.

Parsing is pure (testable on fixtures); fetching is thin HTTP with pagination + cache.
"""

from __future__ import annotations

from . import http, records as rec

BASE = "https://api.openaq.org/v3"
CPCB_PROVIDER_ID = 168  # OpenAQ's provider id for CPCB (India)


# --------------------------------------------------------------------------- #
# Parsing (pure)
# --------------------------------------------------------------------------- #
def parse_locations(payload: dict) -> list[rec.Station]:
    """Build Stations from a /v3/locations response, keeping only AQI sensors."""
    stations: list[rec.Station] = []
    for loc in payload.get("results", []):
        coords = loc.get("coordinates") or {}
        sensors = []
        for s in loc.get("sensors", []):
            param = rec.canonical_pollutant((s.get("parameter") or {}).get("name"))
            if param is None:
                continue
            sensors.append(rec.Sensor(
                sensor_id=s["id"],
                parameter=param,
                units=(s.get("parameter") or {}).get("units", ""),
            ))
        stations.append(rec.Station(
            source="openaq",
            station_id=f"openaq:{loc['id']}",
            name=loc.get("name") or "",
            lat=coords.get("latitude"),
            lon=coords.get("longitude"),
            locality=loc.get("locality"),
            timezone=loc.get("timezone"),
            sensors=sensors,
        ))
    return stations


def parse_sensor_aggregate(
    payload: dict, *, station_id: str, station_name: str | None,
    city: str | None, state: str | None, lat: float | None, lon: float | None,
) -> list[rec.AQRecord]:
    """Parse a /sensors/{id}/days or /hours response into normalized AQRecords."""
    out: list[rec.AQRecord] = []
    for r in payload.get("results", []):
        param = rec.canonical_pollutant((r.get("parameter") or {}).get("name"))
        if param is None:
            continue
        summary = r.get("summary") or {}
        raw_value = summary.get("avg", r.get("value"))
        if raw_value is None:
            continue
        units = (r.get("parameter") or {}).get("units", "")
        value, unit = rec.normalize_concentration(param, raw_value, units)

        period = r.get("period") or {}
        label = period.get("label", "")
        averaging = "1d" if "day" in label else ("1h" if "hour" in label else label or "1h")
        dt_from = period.get("datetimeFrom") or {}
        if averaging == "1d":
            # Daily records key on the LOCAL calendar date (no UTC shift).
            local_date = (dt_from.get("local") or dt_from.get("utc") or "")[:10]
            dt = f"{local_date}T00:00:00Z" if local_date else ""
        else:
            dt = dt_from.get("utc") or ""

        out.append(rec.AQRecord(
            source="openaq", station_id=station_id, station_name=station_name,
            city=city, state=state, lat=lat, lon=lon,
            parameter=param, value=value, unit=unit,
            datetime_utc=dt, averaging=averaging,
            coverage_pct=(r.get("coverage") or {}).get("percentComplete"),
        ))
    return out


# --------------------------------------------------------------------------- #
# Fetching (thin HTTP + pagination)
# --------------------------------------------------------------------------- #
def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key.strip()}


def _as_iso(value: str) -> str:
    """Normalize 'YYYY-MM-DD' to a full ISO-8601 Z timestamp; pass through if already full."""
    return value if "T" in value else f"{value}T00:00:00Z"


def _paginate(url: str, api_key: str, params: dict, *, page_size: int = 1000,
              max_pages: int = 1000, **kw) -> list[dict]:
    """Collect all `results` across pages of a v3 list/aggregate endpoint."""
    results: list[dict] = []
    for page in range(1, max_pages + 1):
        payload = http.get_json(url, params={**params, "limit": page_size, "page": page},
                                headers=_headers(api_key), **kw)
        batch = payload.get("results", [])
        results.extend(batch)
        if len(batch) < page_size:
            break
    return results


def fetch_india_locations(api_key: str, *, cpcb_only: bool = True, **kw) -> list[rec.Station]:
    """All Indian monitoring locations (CPCB provider by default), with their sensors."""
    params: dict = {"iso": "IN"}
    if cpcb_only:
        params["providers_id"] = CPCB_PROVIDER_ID
    results = _paginate(f"{BASE}/locations", api_key, params, **kw)
    return parse_locations({"results": results})


def fetch_sensor_history(
    api_key: str, sensor_id: int, *, date_from: str, date_to: str, period: str = "days",
    station_id: str, station_name: str | None = None, city: str | None = None,
    state: str | None = None, lat: float | None = None, lon: float | None = None, **kw,
) -> list[rec.AQRecord]:
    """Fetch a sensor's aggregated history (period = 'days' or 'hours') and normalize.

    date_from/date_to are ISO strings. NOTE the v3 endpoints filter differently:
      - `/days`  -> `date_from`/`date_to` (date-only)
      - `/hours` -> `datetime_from`/`datetime_to` (full ISO timestamp)
    """
    if period == "hours":
        window = {"datetime_from": _as_iso(date_from), "datetime_to": _as_iso(date_to)}
    else:
        window = {"date_from": date_from[:10], "date_to": date_to[:10]}
    results = _paginate(f"{BASE}/sensors/{sensor_id}/{period}", api_key, window, **kw)
    return parse_sensor_aggregate(
        {"results": results}, station_id=station_id, station_name=station_name,
        city=city, state=state, lat=lat, lon=lon,
    )
