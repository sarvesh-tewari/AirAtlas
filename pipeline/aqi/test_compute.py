"""Tests for the AQI engine (NAQI, US EPA, EU EAQI).

Anchor: the §7 regression case — same 24h concentrations, three standards, three
different labels for identical air. Plus unit-conversion, banding, rounding, the
NAQI city-aggregation rule, validity rules, and top-of-scale handling.
"""

import math

import pytest

from aqi import compute


# Shared §7 input — 24h concentrations in µg/m³ (CO would be mg/m³).
SEVEN = {"pm25": 90, "pm10": 250, "no2": 80, "so2": 40}


# --------------------------------------------------------------------------- #
# §7 regression: identical air, three standards, three labels.
# --------------------------------------------------------------------------- #

def test_naqi_seven_is_moderate_200():
    r = compute.overall("naqi", SEVEN)
    assert r.index == 200
    assert r.category == "Moderate"
    assert set(r.dominant) == {"pm25", "pm10"}


def test_us_seven_is_unhealthy_175():
    r = compute.overall("us", SEVEN)
    assert r.index == 175  # PM2.5-driven, via the 55.5–125.4 -> 151–200 segment
    assert r.category == "Unhealthy"
    assert r.dominant == ["pm25"]


def test_eu_seven_is_very_poor_pm10():
    # Current (2024-revised) EEA bands: PM2.5 90 -> Poor, PM10 250 -> Very Poor.
    r = compute.overall("eu", SEVEN)
    assert r.index is None          # EU is a band, not a 0–500 number
    assert r.band == "Very Poor"
    assert r.category == "Very Poor"
    assert r.dominant == ["pm10"]


# --------------------------------------------------------------------------- #
# Piecewise-linear sub-index formula
# --------------------------------------------------------------------------- #

def test_naqi_subindex_pm25_90_is_200():
    assert compute.sub_index("naqi", "pm25", 90) == 200


def test_naqi_subindex_linear_interpolates():
    # NO2 60 in the 41–80 -> 51–100 segment: 49/39 × 19 + 51 = 74.87 -> 75.
    assert compute.sub_index("naqi", "no2", 60) == 75


def test_naqi_subindex_truncates_before_lookup():
    # 90.9 truncates to 90 before lookup, same as 90.
    assert compute.sub_index("naqi", "pm25", 90.9) == 200


def test_naqi_lower_bound_is_zero():
    assert compute.sub_index("naqi", "pm25", 0) == 0


# --------------------------------------------------------------------------- #
# US EPA µg/m³ -> ppb/ppm conversion + sub-index
# --------------------------------------------------------------------------- #

def test_us_no2_ugm3_to_ppb():
    # 80 µg/m³ NO2 -> ~42.5 ppb at 25°C, 1 atm.
    assert math.isclose(compute.ugm3_to_ppb("no2", 80), 42.52, abs_tol=0.05)


def test_us_so2_ugm3_to_ppb():
    assert math.isclose(compute.ugm3_to_ppb("so2", 40), 15.27, abs_tol=0.05)


def test_us_pm25_subindex_90_is_175():
    assert compute.sub_index("us", "pm25", 90) == 175


def test_us_no2_subindex_low():
    # 80 µg/m³ -> 42 ppb -> Good band -> ~40.
    assert compute.sub_index("us", "no2", 80) == 40


# --------------------------------------------------------------------------- #
# EU EAQI banding (overall = worst band)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "pollutant,conc,band",
    [
        ("pm25", 5, "Good"),
        ("pm25", 90, "Poor"),        # upper edge of Poor (51–90)
        ("pm25", 91, "Very Poor"),
        ("pm25", 200, "Extremely Poor"),
        ("pm10", 250, "Very Poor"),
        ("so2", 40, "Fair"),
    ],
)
def test_eu_band_classification(pollutant, conc, band):
    assert compute.eu_band(pollutant, conc) == band


# --------------------------------------------------------------------------- #
# NAQI validity + city aggregation rules
# --------------------------------------------------------------------------- #

def test_naqi_requires_three_pollutants_incl_pm():
    # Only two pollutants present -> invalid.
    r = compute.overall("naqi", {"no2": 80, "so2": 40})
    assert r.valid is False
    assert r.index is None


def test_naqi_requires_a_pm_pollutant():
    # Three pollutants but none is PM2.5/PM10 -> invalid.
    r = compute.overall("naqi", {"no2": 80, "so2": 40, "o3": 100})
    assert r.valid is False


def test_naqi_city_averages_subindex_across_stations():
    # NAQI city rule: >=3 stations; average each pollutant's sub-index across
    # stations, THEN max across pollutants.
    stations = [
        {"pm25": 60, "pm10": 100, "no2": 40},   # pm25 sub-index 100
        {"pm25": 90, "pm10": 100, "no2": 40},   # pm25 sub-index 200
        {"pm25": 60, "pm10": 100, "no2": 40},   # pm25 sub-index 100
    ]
    r = compute.city_index_naqi(stations)
    # pm25 avg sub-index = (100+200+100)/3 = 133; pm10 = 50; no2 = 50 -> overall 133.
    assert r.valid is True
    assert r.index == 133
    assert r.dominant == ["pm25"]


def test_naqi_city_requires_three_stations():
    stations = [{"pm25": 60, "pm10": 100, "no2": 40}] * 2
    r = compute.city_index_naqi(stations)
    assert r.valid is False


# --------------------------------------------------------------------------- #
# Top-of-scale handling
# --------------------------------------------------------------------------- #

def test_naqi_above_scale_caps_at_500():
    r = compute.overall("naqi", {"pm25": 9999, "pm10": 9999, "no2": 9999})
    assert r.index == 500
    assert r.off_scale is True
    assert r.category == "Severe"
