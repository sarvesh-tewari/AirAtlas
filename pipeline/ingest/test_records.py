"""Tests for the normalized ingestion schema + unit helpers."""

import math

from ingest import records as rec


def test_canonical_pollutant_maps_source_names():
    assert rec.canonical_pollutant("PM2.5") == "pm25"
    assert rec.canonical_pollutant("pm25") == "pm25"
    assert rec.canonical_pollutant("OZONE") == "o3"
    assert rec.canonical_pollutant("o3") == "o3"
    assert rec.canonical_pollutant("NH3") == "nh3"


def test_canonical_pollutant_unknown_is_none():
    # nox / no / weather params are not AQI pollutants we track.
    assert rec.canonical_pollutant("NOx") is None
    assert rec.canonical_pollutant("temperature") is None


def test_ppb_to_ugm3_no2():
    # Inverse of the engine's µg/m³->ppb: 42.52 ppb NO2 -> ~80 µg/m³.
    assert math.isclose(rec.ppb_to_ugm3("no2", 42.52), 80.0, abs_tol=0.1)


def test_normalize_concentration_ppb_to_ugm3():
    value, unit = rec.normalize_concentration("no2", 42.52, "ppb")
    assert math.isclose(value, 80.0, abs_tol=0.1)
    assert unit == "µg/m³"


def test_normalize_concentration_co_ppb_to_mgm3():
    # CO is stored in mg/m³.
    value, unit = rec.normalize_concentration("co", 1000.0, "ppb")
    assert unit == "mg/m³"
    assert value < 2.0  # 1000 ppb CO ~= 1.15 mg/m³


def test_normalize_concentration_already_ugm3_passthrough():
    assert rec.normalize_concentration("pm25", 90.0, "µg/m³") == (90.0, "µg/m³")
