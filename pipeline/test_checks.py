"""Tests for CI health checks."""

import datetime as dt
import json

import checks


def _now():
    return dt.datetime(2026, 6, 11, 12, 0, 0, tzinfo=dt.timezone.utc)


def test_age_none_when_no_live_files(tmp_path):
    assert checks.newest_live_age_hours(tmp_path, now=_now()) is None


def test_age_is_newest_snapshot(tmp_path):
    (tmp_path / "delhi.json").write_text(json.dumps({"updated_utc": "2026-06-11T02:00:00Z"}))
    (tmp_path / "mumbai.json").write_text(json.dumps({"updated_utc": "2026-06-11T10:00:00Z"}))
    age = checks.newest_live_age_hours(tmp_path, now=_now())
    assert abs(age - 2.0) < 0.01          # newest is 10:00Z -> 2h before 12:00Z


def test_age_ignores_unparseable(tmp_path):
    (tmp_path / "x.json").write_text(json.dumps({"updated_utc": None}))
    (tmp_path / "y.json").write_text("not json")
    assert checks.newest_live_age_hours(tmp_path, now=_now()) is None


def test_coverage_verdict_ok_when_stable():
    ok, msg = checks.coverage_verdict(286, 286, 467, 467)
    assert ok is True
    assert msg.startswith("OK:")


def test_coverage_verdict_city_drop_over_5pct_trips():
    ok, msg = checks.coverage_verdict(286, 240, 467, 467)  # cities -16%
    assert ok is False
    assert "COVERAGE DROP" in msg and "cities" in msg


def test_coverage_verdict_city_drop_under_5pct_ok():
    ok, _ = checks.coverage_verdict(286, 276, 467, 467)  # cities -3.5%
    assert ok is True


def test_coverage_verdict_station_drop_over_10pct_trips():
    ok, msg = checks.coverage_verdict(286, 286, 467, 400)  # stations -14%
    assert ok is False
    assert "stations" in msg


def test_coverage_verdict_per_metric_thresholds():
    # a 6% drop trips cities (>5%) but NOT stations (<10%)
    ok_city, msg_city = checks.coverage_verdict(100, 94, 100, 100)
    ok_st, _ = checks.coverage_verdict(100, 100, 100, 94)
    assert ok_city is False and "cities" in msg_city and "stations" not in msg_city
    assert ok_st is True


def test_coverage_verdict_growth_never_trips():
    ok, _ = checks.coverage_verdict(286, 300, 467, 480)
    assert ok is True


def test_coverage_verdict_zero_prior_skips_metric():
    # no divide-by-zero; a None/0 prior means that metric is not evaluated
    ok, _ = checks.coverage_verdict(0, 50, None, 50)
    assert ok is True


def test_read_coverage(tmp_path):
    (tmp_path / "city_list.json").write_text(json.dumps({"cities": ["a", "b", "c"]}))
    (tmp_path / "cities.json").write_text(json.dumps([{"n_stations": 2}, {"n_stations": 3}]))
    assert checks.read_coverage(tmp_path) == (3, 5)


def test_read_coverage_missing_files(tmp_path):
    assert checks.read_coverage(tmp_path) == (None, None)
