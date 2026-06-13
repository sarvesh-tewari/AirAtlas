"""Tests for station->city aggregation + sensor-duplicate merging."""

from ingest.records import AQRecord
from transform import aggregate as agg


def _aq(station, param, dt, value, *, city=None, cov=None, averaging="1d"):
    return AQRecord(source="openaq", station_id=station, station_name=station,
                    city=city, state=None, lat=None, lon=None, parameter=param,
                    value=value, unit="µg/m³", datetime_utc=dt, averaging=averaging,
                    coverage_pct=cov)


def test_merge_sensor_duplicates_prefers_highest_coverage():
    # Same station+pollutant+day from two sensors -> keep the better-covered one.
    recs = [
        _aq("openaq:17", "pm25", "2026-06-01T00:00:00Z", 80.0, cov=60.0),
        _aq("openaq:17", "pm25", "2026-06-01T00:00:00Z", 90.0, cov=98.0),
    ]
    merged = agg.merge_sensor_duplicates(recs)
    assert len(merged) == 1
    assert merged[0].value == 90.0


def test_drop_implausible_removes_out_of_range_and_pm25_over_pm10():
    recs = [
        _aq("openaq:1", "so2", "2026-06-01T00:00:00Z", 2991.0),   # > cap -> dropped
        _aq("openaq:1", "pm25", "2026-06-01T00:00:00Z", 738.8),   # > pm10 -> dropped
        _aq("openaq:1", "pm10", "2026-06-01T00:00:00Z", 37.4),    # kept
        _aq("openaq:1", "no2", "2026-06-01T00:00:00Z", 25.0),     # kept
    ]
    kept = {(r.parameter, round(r.value, 1)) for r in agg.drop_implausible(recs)}
    assert kept == {("pm10", 37.4), ("no2", 25.0)}


def test_drop_implausible_keeps_valid_pm25_below_pm10():
    recs = [
        _aq("openaq:1", "pm25", "2026-06-01T00:00:00Z", 180.0),
        _aq("openaq:1", "pm10", "2026-06-01T00:00:00Z", 250.0),
    ]
    assert len(agg.drop_implausible(recs)) == 2


def test_aggregate_drops_implausible_before_averaging():
    # A garbage PM2.5 (>PM10) at one station must not inflate the city mean.
    recs = [
        _aq("openaq:1", "pm25", "2026-06-01T00:00:00Z", 738.8, city="Delhi"),
        _aq("openaq:1", "pm10", "2026-06-01T00:00:00Z", 40.0, city="Delhi"),
        _aq("openaq:2", "pm25", "2026-06-01T00:00:00Z", 60.0, city="Delhi"),
        _aq("openaq:2", "pm10", "2026-06-01T00:00:00Z", 90.0, city="Delhi"),
    ]
    city = {(r.parameter): r for r in agg.aggregate_to_city(recs)}
    assert city["pm25"].value == 60.0   # the 738.8 was dropped, not averaged in
    assert city["pm25"].n_stations == 1


def test_aggregate_to_city_means_across_stations():
    recs = [
        _aq("openaq:1", "pm25", "2026-06-01T00:00:00Z", 60.0, city="Delhi", cov=100.0),
        _aq("openaq:2", "pm25", "2026-06-01T00:00:00Z", 90.0, city="Delhi", cov=100.0),
        _aq("openaq:3", "pm25", "2026-06-01T00:00:00Z", 120.0, city="Delhi", cov=100.0),
    ]
    city = agg.aggregate_to_city(recs)
    assert len(city) == 1
    r = city[0]
    assert r.city == "Delhi"
    assert r.parameter == "pm25"
    assert r.value == 90.0          # mean of 60,90,120
    assert r.n_stations == 3


def test_aggregate_to_city_resolves_city_from_map():
    # OpenAQ records carry no city; a station->city map supplies it.
    recs = [_aq("openaq:17", "pm25", "2026-06-01T00:00:00Z", 50.0, city=None, cov=100.0)]
    city = agg.aggregate_to_city(recs, station_city={"openaq:17": "Delhi"})
    assert city[0].city == "Delhi"


def test_aggregate_to_city_skips_unmapped_stations():
    recs = [_aq("openaq:999", "pm25", "2026-06-01T00:00:00Z", 50.0, city=None)]
    assert agg.aggregate_to_city(recs) == []


def test_aggregate_to_city_keeps_periods_separate():
    recs = [
        _aq("openaq:1", "pm25", "2026-06-01T00:00:00Z", 60.0, city="Delhi", averaging="1d"),
        _aq("openaq:1", "pm25", "2026-06-02T00:00:00Z", 80.0, city="Delhi", averaging="1d"),
    ]
    city = agg.aggregate_to_city(recs)
    assert {r.datetime_utc for r in city} == {"2026-06-01T00:00:00Z", "2026-06-02T00:00:00Z"}


def test_aggregate_to_city_min_coverage_filters_thin_station_days():
    recs = [
        _aq("openaq:1", "pm25", "2026-06-01T00:00:00Z", 60.0, city="Delhi", cov=20.0),
        _aq("openaq:2", "pm25", "2026-06-01T00:00:00Z", 90.0, city="Delhi", cov=100.0),
    ]
    city = agg.aggregate_to_city(recs, min_coverage=50.0)
    assert city[0].n_stations == 1   # the 20%-coverage station-day was dropped
    assert city[0].value == 90.0
