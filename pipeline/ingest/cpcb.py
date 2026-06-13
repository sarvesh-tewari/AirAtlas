"""CPCB live fetch via data.gov.in + parsing.

Resource: "Real time Air Quality Index from various locations"
(id 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69). Reads DATA_GOV_IN_KEY from the environment.

The feed is a *snapshot with no memory* — one record per (station, pollutant) with
min/max/avg and a `last_update` timestamp in IST. We keep today's value; OpenAQ provides
history (today=CPCB, history=OpenAQ seam, handled in transform/reconcile).

Schema robustness: data.gov.in has shipped two field-name variants over time
(`pollutant_avg`/`pollutant_min`/… vs `avg_value`/`min_value`/… with `latitude`). The
parser accepts both. Missing values are the string "NA". Concentrations are µg/m³
(CO in mg/m³); OZONE maps to o3.

Parsing is pure (testable on a fixture); fetching is thin HTTP with retry + keep-last-good.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import http, records as rec

RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
BASE = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

_IST = timezone(timedelta(hours=5, minutes=30))


def _canon_pollutant(pollutant_id: str) -> str | None:
    return rec.canonical_pollutant(pollutant_id)


def _na(value) -> bool:
    return value is None or str(value).strip().upper() in ("NA", "", "NONE")


def _num(value) -> float | None:
    if _na(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ist_to_utc_z(last_update: str) -> str | None:
    """'11-06-2026 18:00:00' (IST) -> '2026-06-11T12:30:00Z'."""
    if _na(last_update):
        return None
    try:
        naive = datetime.strptime(last_update.strip(), "%d-%m-%Y %H:%M:%S")
    except ValueError:
        return None
    return naive.replace(tzinfo=_IST).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_live(payload: dict) -> list[rec.AQRecord]:
    """Parse a data.gov.in response into normalized live AQRecords.

    Records whose average value is missing ('NA') are skipped.
    """
    out: list[rec.AQRecord] = []
    for r in payload.get("records", []):
        param = _canon_pollutant(r.get("pollutant_id"))
        if param is None:
            continue
        # Dual schema: pollutant_avg/… or avg_value/….
        avg = _num(r.get("pollutant_avg", r.get("avg_value")))
        if avg is None:
            continue  # no usable value

        value, unit = rec.normalize_concentration(param, avg, r.get("pollutant_unit"))
        out.append(rec.AQRecord(
            source="cpcb",
            station_id=f"cpcb:{r.get('station')}",
            station_name=r.get("station"),
            city=r.get("city"),
            state=r.get("state"),
            lat=_num(r.get("latitude", r.get("lat"))),
            lon=_num(r.get("longitude", r.get("lon", r.get("long")))),
            parameter=param,
            value=value,
            unit=unit,
            datetime_utc=_ist_to_utc_z(r.get("last_update")) or "",
            averaging="live",
        ))
    return out


# --------------------------------------------------------------------------- #
# Fetching (thin HTTP + retry). Keep-last-good is the orchestrator's job (Phase 5).
# --------------------------------------------------------------------------- #
def fetch_live(api_key: str, *, limit: int = 5000, **kw) -> list[rec.AQRecord]:
    """Fetch the full nationwide live snapshot and normalize it.

    Live data is not cached by default (use_cache=False) so each run is fresh.
    Raises RuntimeError if data.gov.in is unreachable after retries.
    """
    payload = http.get_json(
        BASE, params={"api-key": api_key.strip(), "format": "json", "limit": limit},
        use_cache=kw.pop("use_cache", False), **kw,
    )
    return parse_live(payload)
