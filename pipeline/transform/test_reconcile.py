"""Tests for the today=CPCB / history=OpenAQ reconciliation seam."""

from transform.aggregate import CityPollutantRecord
from transform import reconcile as rec


def _city(city, param, date, value, source, averaging="1d"):
    return CityPollutantRecord(city=city, parameter=param,
                               datetime_utc=f"{date}T00:00:00Z", averaging=averaging,
                               value=value, unit="µg/m³", n_stations=3,
                               coverage_pct=100.0, source=source)


def test_reconcile_today_from_cpcb_history_from_openaq():
    history = [
        _city("Delhi", "pm25", "2026-06-09", 70.0, "openaq"),
        _city("Delhi", "pm25", "2026-06-10", 80.0, "openaq"),
    ]
    today = [_city("Delhi", "pm25", "2026-06-11", 90.0, "cpcb")]
    out = rec.reconcile_daily(today_cpcb=today, history_openaq=history, today="2026-06-11")
    by_date = {r.datetime_utc[:10]: r for r in out}
    assert by_date["2026-06-09"].source == "openaq"
    assert by_date["2026-06-11"].source == "cpcb"
    assert by_date["2026-06-11"].value == 90.0
    assert len(out) == 3


def test_reconcile_drops_openaq_rows_on_or_after_today():
    # OpenAQ sometimes already has a (partial) row for today -> CPCB must win, no overlap.
    history = [
        _city("Delhi", "pm25", "2026-06-10", 80.0, "openaq"),
        _city("Delhi", "pm25", "2026-06-11", 55.0, "openaq"),   # stray today row
    ]
    today = [_city("Delhi", "pm25", "2026-06-11", 90.0, "cpcb")]
    out = rec.reconcile_daily(today_cpcb=today, history_openaq=history, today="2026-06-11")
    today_rows = [r for r in out if r.datetime_utc[:10] == "2026-06-11"]
    assert len(today_rows) == 1
    assert today_rows[0].source == "cpcb"
    assert today_rows[0].value == 90.0


def test_reconcile_sorted_by_city_param_date():
    history = [
        _city("Mumbai", "pm25", "2026-06-10", 40.0, "openaq"),
        _city("Delhi", "pm10", "2026-06-09", 200.0, "openaq"),
        _city("Delhi", "pm25", "2026-06-10", 80.0, "openaq"),
    ]
    out = rec.reconcile_daily(today_cpcb=[], history_openaq=history, today="2026-06-11")
    keys = [(r.city, r.parameter, r.datetime_utc[:10]) for r in out]
    assert keys == sorted(keys)
