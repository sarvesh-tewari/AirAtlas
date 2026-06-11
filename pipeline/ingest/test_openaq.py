"""Tests for OpenAQ v3 parsing (against real captured fixtures)."""

import json
import pathlib

from ingest import openaq

FX = pathlib.Path(__file__).parent / "fixtures" / "openaq"


def _load(name):
    return json.loads((FX / name).read_text())


def test_parse_locations_builds_stations_with_sensors():
    stations = openaq.parse_locations(_load("locations_in.json"))
    assert stations
    s = stations[0]
    assert s.source == "openaq"
    assert s.station_id == "openaq:12"
    assert s.lat is not None and s.lon is not None
    # SPARTAN IIT-Kanpur has a pm25 sensor.
    assert any(sensor.parameter == "pm25" for sensor in s.sensors)


def test_parse_locations_skips_non_aqi_sensors():
    # location_17 has temperature/wind/nox sensors that must NOT become pollutants.
    stations = openaq.parse_locations(_load("locations_in.json"))
    for s in stations:
        for sensor in s.sensors:
            assert sensor.parameter in {"pm25", "pm10", "no2", "so2", "o3", "co", "nh3"}


def test_parse_sensor_aggregate_daily():
    recs = openaq.parse_sensor_aggregate(
        _load("sensor_days.json"),
        station_id="openaq:17", station_name="R K Puram", city="Delhi", state="Delhi",
        lat=28.56, lon=77.18,
    )
    assert recs
    r = recs[0]
    assert r.source == "openaq"
    assert r.parameter == "pm25"
    assert r.unit == "µg/m³"
    assert r.averaging == "1d"
    assert abs(r.value - 78.05) < 0.1          # uses summary.avg
    assert r.coverage_pct == 96.0
    assert r.datetime_utc.endswith("Z")


def test_parse_sensor_aggregate_converts_ppb():
    # A synthetic NO2 day record reported in ppb must be normalized to µg/m³.
    payload = {
        "results": [{
            "value": 42.52,
            "parameter": {"name": "no2", "units": "ppb"},
            "period": {"label": "1day",
                       "datetimeFrom": {"utc": "2026-06-10T18:30:00Z", "local": "2026-06-11T00:00:00+05:30"}},
            "summary": {"avg": 42.52},
            "coverage": {"percentComplete": 100.0},
        }]
    }
    recs = openaq.parse_sensor_aggregate(payload, station_id="openaq:17", station_name="x",
                                         city="Delhi", state="Delhi", lat=1.0, lon=2.0)
    assert recs[0].unit == "µg/m³"
    assert abs(recs[0].value - 80.0) < 0.2     # 42.52 ppb NO2 -> ~80 µg/m³
