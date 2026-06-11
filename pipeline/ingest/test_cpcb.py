"""Tests for CPCB (data.gov.in) live parsing.

The data.gov.in API was down at build time, so this parses a hand-built fixture that
mirrors the documented schema (both field-name variants + an 'NA' missing value).
Live verification happens once the API recovers.
"""

import json
import pathlib

from ingest import cpcb

FX = pathlib.Path(__file__).parent / "fixtures" / "cpcb"


def _load(name):
    return json.loads((FX / name).read_text())


def test_parse_live_basic_record():
    recs = cpcb.parse_live(_load("live_sample.json"))
    by_param = {(r.station_name, r.parameter): r for r in recs}
    pm25 = by_param[("R K Puram, Delhi - DPCC", "pm25")]
    assert pm25.source == "cpcb"
    assert pm25.value == 90.0
    assert pm25.unit == "µg/m³"
    assert pm25.city == "Delhi"
    assert pm25.state == "Delhi"
    assert pm25.averaging == "live"
    assert abs(pm25.lat - 28.5631) < 1e-4


def test_parse_live_converts_ist_to_utc():
    recs = cpcb.parse_live(_load("live_sample.json"))
    pm25 = next(r for r in recs if r.parameter == "pm25")
    # last_update "11-06-2026 18:00:00" IST -> 12:30:00 UTC.
    assert pm25.datetime_utc == "2026-06-11T12:30:00Z"


def test_parse_live_skips_na_values():
    recs = cpcb.parse_live(_load("live_sample.json"))
    params = {r.parameter for r in recs}
    assert "o3" not in params              # OZONE row was all-NA -> skipped
    assert {"pm25", "pm10", "no2"} <= params


def test_parse_live_handles_newer_field_variant():
    # The Mumbai NO2 row uses avg_value/min_value + latitude (newer schema).
    recs = cpcb.parse_live(_load("live_sample.json"))
    no2 = next(r for r in recs if r.parameter == "no2")
    assert no2.value == 40.0
    assert no2.city == "Mumbai"


def test_parse_live_maps_ozone_to_o3():
    # Sanity: the canonical mapping is applied (OZONE -> o3) even though this row is NA.
    assert cpcb._canon_pollutant("OZONE") == "o3"
