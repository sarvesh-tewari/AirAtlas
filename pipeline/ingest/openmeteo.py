"""Open-Meteo fetch: current weather (Forecast API) + historical (Archive/ERA5) + parsing.

No API key required. Forecast API gives `current` + `hourly` (columnar arrays); the
Archive API gives `daily` (columnar). Wind is normalized to m/s regardless of the unit
the payload reports (Open-Meteo defaults to km/h unless wind_speed_unit=ms is requested).

Parsing is pure (testable on fixtures); fetching is thin HTTP with cache.
"""

from __future__ import annotations

from . import http, records as rec

FORECAST_BASE = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_BASE = "https://archive-api.open-meteo.com/v1/archive"

_HOURLY = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m"
_CURRENT = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m"
_DAILY = ("temperature_2m_mean,temperature_2m_max,temperature_2m_min,"
          "relative_humidity_2m_mean,precipitation_sum,wind_speed_10m_max")


def _wind_to_ms(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    u = (unit or "").lower()
    if "km/h" in u or "kmh" in u:
        return value / 3.6
    if "mph" in u:
        return value * 0.44704
    if "kn" in u:
        return value * 0.514444
    return value  # already m/s


def _to_utc_z(local_iso: str, utc_offset_seconds: int) -> str:
    """Convert an Open-Meteo local timestamp (no tz) to an ISO-8601 Z string."""
    from datetime import datetime, timedelta, timezone
    # Times may be "YYYY-MM-DDTHH:MM" (hourly/current) or "YYYY-MM-DD" (daily).
    fmt = "%Y-%m-%dT%H:%M" if "T" in local_iso else "%Y-%m-%d"
    naive = datetime.strptime(local_iso, fmt)
    utc = naive - timedelta(seconds=utc_offset_seconds)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_current(payload: dict) -> rec.WeatherRecord:
    cur = payload["current"]
    units = payload.get("current_units", {})
    offset = payload.get("utc_offset_seconds", 0)
    return rec.WeatherRecord(
        source="open-meteo",
        lat=payload["latitude"], lon=payload["longitude"],
        datetime_utc=_to_utc_z(cur["time"], offset),
        averaging="live",
        temp_c=cur.get("temperature_2m"),
        rh_pct=cur.get("relative_humidity_2m"),
        precip_mm=cur.get("precipitation"),
        wind_speed_ms=_wind_to_ms(cur.get("wind_speed_10m"), units.get("wind_speed_10m")),
        wind_dir_deg=cur.get("wind_direction_10m"),
    )


def parse_archive_daily(payload: dict) -> list[rec.WeatherRecord]:
    daily = payload["daily"]
    units = payload.get("daily_units", {})
    lat, lon = payload["latitude"], payload["longitude"]
    out: list[rec.WeatherRecord] = []
    for i, day in enumerate(daily["time"]):
        def col(name):
            vals = daily.get(name)
            return vals[i] if vals is not None else None
        out.append(rec.WeatherRecord(
            source="open-meteo", lat=lat, lon=lon,
            # Daily records key on the LOCAL calendar date (no UTC shift).
            datetime_utc=f"{day}T00:00:00Z", averaging="1d",
            temp_c=col("temperature_2m_mean"),
            temp_min_c=col("temperature_2m_min"),
            temp_max_c=col("temperature_2m_max"),
            rh_pct=col("relative_humidity_2m_mean"),
            precip_mm=col("precipitation_sum"),
            wind_speed_ms=_wind_to_ms(col("wind_speed_10m_max"), units.get("wind_speed_10m_max")),
        ))
    return out


# --------------------------------------------------------------------------- #
# Fetching (thin HTTP). No API key required.
# --------------------------------------------------------------------------- #
def fetch_current(lat: float, lon: float, **kw) -> rec.WeatherRecord:
    payload = http.get_json(FORECAST_BASE, params={
        "latitude": lat, "longitude": lon,
        "current": _CURRENT, "wind_speed_unit": "ms", "timezone": "auto",
    }, use_cache=False, **kw)
    return parse_current(payload)


def fetch_recent_hourly(lat: float, lon: float, *, past_days: int = 92, **kw) -> dict:
    """Recent hourly weather (for the AQI↔weather overlay). Returns the raw payload."""
    return http.get_json(FORECAST_BASE, params={
        "latitude": lat, "longitude": lon, "hourly": _HOURLY,
        "past_days": past_days, "forecast_days": 1,
        "wind_speed_unit": "ms", "timezone": "auto",
    }, **kw)


def fetch_archive_daily(lat: float, lon: float, *, start_date: str, end_date: str,
                        **kw) -> list[rec.WeatherRecord]:
    payload = http.get_json(ARCHIVE_BASE, params={
        "latitude": lat, "longitude": lon,
        "start_date": start_date, "end_date": end_date,
        "daily": _DAILY, "wind_speed_unit": "ms", "timezone": "auto",
    }, **kw)
    return parse_archive_daily(payload)
