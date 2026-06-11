"""Reconciliation seam: today = CPCB, history (<= yesterday) = OpenAQ.

CPCB is the authoritative live number Indian users trust, but it has no memory; OpenAQ
keeps the multi-year history. To avoid a visible contradiction for the same day, we stitch:
  - dates strictly before `today`  -> OpenAQ
  - `today`                        -> CPCB (any OpenAQ row for today is dropped)
Every output row carries its `source` so the frontend can label the seam.
"""

from __future__ import annotations

from .aggregate import CityPollutantRecord


def _date(r: CityPollutantRecord) -> str:
    return r.datetime_utc[:10]


def reconcile_daily(
    *,
    today_cpcb: list[CityPollutantRecord],
    history_openaq: list[CityPollutantRecord],
    today: str,
) -> list[CityPollutantRecord]:
    """Merge the CPCB live snapshot (today) with the OpenAQ daily history (< today).

    `today` is a 'YYYY-MM-DD' string (the local/IST current date). Returns a single daily
    series per (city, parameter), sorted by (city, parameter, date), source-tagged.
    """
    out: list[CityPollutantRecord] = []

    # History: keep strictly-before-today rows, tagged openaq.
    for r in history_openaq:
        if _date(r) < today:
            out.append(_tagged(r, "openaq"))

    # Today: CPCB wins. Normalize its date key to today's local date.
    for r in today_cpcb:
        out.append(_tagged(r, "cpcb", date=today))

    out.sort(key=lambda r: (r.city, r.parameter, r.datetime_utc))
    return out


def _tagged(r: CityPollutantRecord, source: str, *, date: str | None = None) -> CityPollutantRecord:
    dt = f"{date}T00:00:00Z" if date else r.datetime_utc
    return CityPollutantRecord(
        city=r.city, parameter=r.parameter, datetime_utc=dt, averaging=r.averaging,
        value=r.value, unit=r.unit, n_stations=r.n_stations,
        coverage_pct=r.coverage_pct, source=source,
    )
