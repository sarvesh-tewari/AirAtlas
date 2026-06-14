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


def test_dn_park_misparse_resolves_to_lucknow_via_alias():
    # "Lalbagh, DN Park" (Lucknow) has no "- <Board>" suffix, so the parser takes the last
    # comma-chunk ("DN Park", a sub-area) as the city. The alias corrects this known misparse.
    assert citymap.city_from_station_name("Lalbagh, DN Park") == "DN Park"
    stations = [_st("openaq:354", "Lalbagh, DN Park")]
    mapping, _ = citymap.build_station_city_map(stations, aliases={"DN Park": "Lucknow"})
    assert mapping == {"openaq:354": "Lucknow"}


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


def test_sector_dash_number_misparse_fixed_by_alias():
    # "Sector - 125, Noida..." splits on " - " so the parser yields "125, Noida, UP" as the city.
    # The curated city alias normalizes that (and the Greater Noida variant) back to a clean name.
    stations = [
        _st("openaq:10", "Sector - 125, Noida, UP - UPPCB"),
        _st("openaq:11", "Knowledge Park - III, Greater Noida - UPPCB"),
    ]
    raw, _ = citymap.build_station_city_map(stations)
    assert raw["openaq:10"] == "125, Noida, UP"          # the misparse we saw in production
    assert raw["openaq:11"] == "III, Greater Noida"
    fixed, _ = citymap.build_station_city_map(stations, aliases={
        "125, Noida, UP": "Noida",
        "III, Greater Noida": "Greater Noida",
    })
    assert fixed["openaq:10"] == "Noida"
    assert fixed["openaq:11"] == "Greater Noida"


def test_build_map_reports_unmapped():
    stations = [_st("openaq:3", "IGI Airport")]
    mapping, unmapped = citymap.build_station_city_map(stations)
    assert mapping == {}
    assert unmapped == ["openaq:3"]
