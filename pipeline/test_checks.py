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
