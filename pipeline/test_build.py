"""Tests for meta-assembly helpers in build.py."""

import build
from ingest.records import Sensor, Station


def _st(sid, name, sensors):
    return Station(source="openaq", station_id=sid, name=name, lat=1.0, lon=2.0, sensors=sensors)


def test_stations_cache_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "STATIONS_CACHE", tmp_path / "stations.json")
    build._save_stations([_st("openaq:1", "R K Puram, Delhi - DPCC", [Sensor(7, "pm25", "µg/m³")])])
    out = build._load_stations()
    assert len(out) == 1 and out[0].station_id == "openaq:1"
    assert out[0].sensors[0].sensor_id == 7 and out[0].sensors[0].parameter == "pm25"


def test_discover_falls_back_to_cache_when_locations_down(tmp_path, monkeypatch):
    # A transient OpenAQ /locations outage must not fail the run: fall back to the last-good
    # station list persisted on a prior successful run.
    monkeypatch.setattr(build, "STATIONS_CACHE", tmp_path / "stations.json")
    build._save_stations([_st("openaq:1", "R K Puram, Delhi - DPCC", [Sensor(7, "pm25", "µg/m³")])])

    def boom(*a, **k):
        raise RuntimeError("GET failed after 8 attempts")

    monkeypatch.setattr(build.openaq, "fetch_india_locations", boom)
    stations, mapping, unmapped = build.discover("key")
    assert [s.station_id for s in stations] == ["openaq:1"]
    assert mapping == {"openaq:1": "Delhi"}


def test_discover_raises_when_down_and_no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "STATIONS_CACHE", tmp_path / "stations.json")  # absent

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(build.openaq, "fetch_india_locations", boom)
    try:
        build.discover("key")
        assert False, "expected discover to raise with no cache to fall back on"
    except RuntimeError:
        pass


def test_http_status_extracts_code():
    import httpx
    import build
    req = httpx.Request("GET", "https://x/y")
    resp = httpx.Response(422, request=req)
    err = httpx.HTTPStatusError("422", request=req, response=resp)
    assert build._http_status(err) == "HTTP 422"
    # wrapped in a RuntimeError (the http.py path) -> unwrap via __cause__
    wrapped = RuntimeError("GET failed")
    wrapped.__cause__ = err
    assert build._http_status(wrapped) == "HTTP 422"
    assert build._http_status(ValueError("nope")) == "ValueError"


def test_fetch_city_aq_prints_summary(monkeypatch, capsys):
    import build
    from ingest.records import Station, Sensor
    st = Station(source="openaq", station_id="s1", name="S1", lat=1.0, lon=2.0,
                 locality=None, city=None, state=None, timezone="Asia/Kolkata",
                 sensors=[Sensor(sensor_id=1, parameter="pm25", units="µg/m³")])
    monkeypatch.setattr(build.openaq, "fetch_sensor_history",
                        lambda *a, **k: [])  # empty -> n_empty path
    build.fetch_city_aq("key", [st], {"s1": "Pune"}, date_from="2026-06-18",
                        date_to="2026-06-19", period="hours")
    out = capsys.readouterr().out
    assert "[build] hours:" in out
    assert "1 sensors" in out


def test_merge_centroids_fills_prior_cities_not_in_this_run():
    # This run only discovered Mumbai's stations, so `centroids` lacks Delhi. Delhi was published
    # by an earlier batch, so its centroid lives in the prior cities.json — recover it, or Delhi's
    # map marker loses its lat/lon when meta is rebuilt from the full on-disk union.
    centroids = {"Mumbai": (19.07, 72.87)}
    prior_index = [
        {"city": "Delhi", "lat": 28.61, "lon": 77.20},
        {"city": "Mumbai", "lat": 0.0, "lon": 0.0},  # stale; this run's value must win
    ]
    merged = build.merge_centroids(centroids, prior_index)
    assert merged["Delhi"] == (28.61, 77.20)        # recovered from prior
    assert merged["Mumbai"] == (19.07, 72.87)       # this run's fresh value preserved


def test_latest_daily_date_picks_max():
    rows = [{"city": "A", "date": "2026-06-14"}, {"city": "B", "date": "2026-06-20"},
            {"city": "A", "date": "2026-06-15"}]
    assert build.latest_daily_date(rows) == "2026-06-20"


def test_latest_daily_date_empty():
    assert build.latest_daily_date([]) is None


def test_latest_daily_date_skips_rows_without_date():
    rows = [{"city": "A"}, {"city": "B", "date": "2026-06-19"}, {"city": "C", "date": None}]
    assert build.latest_daily_date(rows) == "2026-06-19"
