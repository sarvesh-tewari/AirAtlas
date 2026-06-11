"""Tests for deriving a station->city map from CPCB-style station names."""

from ingest.records import Station
from transform import citymap


def _st(station_id, name):
    return Station(source="openaq", station_id=station_id, name=name)


def test_city_from_comma_format():
    assert citymap.city_from_station_name("R K Puram, Delhi - DPCC") == "Delhi"
    assert citymap.city_from_station_name("Anand Vihar, New Delhi - DPCC") == "New Delhi"


def test_city_from_dash_format():
    # "<Area> - <City> - <Board>"
    assert citymap.city_from_station_name("Collectorate - Gaya - BSPCB") == "Gaya"


def test_city_unparseable_returns_none():
    assert citymap.city_from_station_name("IGI Airport") is None
    assert citymap.city_from_station_name("Victoria Memorial - WBSPCB") is None


def test_build_map_applies_overrides_and_aliases():
    stations = [
        _st("openaq:1", "R K Puram, Delhi - DPCC"),
        _st("openaq:2", "Anand Vihar, New Delhi - DPCC"),
        _st("openaq:3", "IGI Airport"),                       # unparseable -> override
    ]
    mapping, unmapped = citymap.build_station_city_map(
        stations,
        overrides={"openaq:3": "Delhi"},
        aliases={"New Delhi": "Delhi"},
    )
    assert mapping == {"openaq:1": "Delhi", "openaq:2": "Delhi", "openaq:3": "Delhi"}
    assert unmapped == []


def test_build_map_reports_unmapped():
    stations = [_st("openaq:3", "IGI Airport")]
    mapping, unmapped = citymap.build_station_city_map(stations)
    assert mapping == {}
    assert unmapped == ["openaq:3"]
