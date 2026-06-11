"""Tests for Open-Meteo parsing (against real captured fixtures)."""

import json
import pathlib

from ingest import openmeteo

FX = pathlib.Path(__file__).parent / "fixtures" / "openmeteo"


def _load(name):
    return json.loads((FX / name).read_text())


def test_parse_current_weather():
    r = openmeteo.parse_current(_load("forecast.json"))
    assert r.source == "open-meteo"
    assert r.averaging == "live"
    assert r.temp_c == 30.1
    assert r.rh_pct == 66
    # wind captured in km/h in the fixture -> normalized to m/s (10.3 / 3.6).
    assert abs(r.wind_speed_ms - 2.86) < 0.02
    assert r.datetime_utc.endswith("Z")


def test_parse_archive_daily():
    recs = openmeteo.parse_archive_daily(_load("archive_daily.json"))
    assert len(recs) == 5
    first = recs[0]
    assert first.source == "open-meteo"
    assert first.averaging == "1d"
    assert first.temp_c == 10.1          # temperature_2m_mean
    assert first.temp_min_c == 3.0
    assert first.temp_max_c == 17.7
    assert first.precip_mm == 0.0
    assert abs(first.wind_speed_ms - (10.5 / 3.6)) < 0.02
    assert first.datetime_utc.startswith("2020-01-01")
