"""Tests for assembling wide, storage-ready rows (concentrations + precomputed AQI + weather)."""

from ingest.records import WeatherRecord
from transform.aggregate import CityPollutantRecord
from transform import storage


def _c(city, param, date, value, source="openaq", unit="µg/m³"):
    return CityPollutantRecord(city=city, parameter=param, datetime_utc=f"{date}T00:00:00Z",
                               averaging="1d", value=value, unit=unit, n_stations=3,
                               coverage_pct=100.0, source=source)


def test_assemble_daily_row_has_concentrations_and_all_three_aqis():
    recs = [
        _c("Delhi", "pm25", "2026-06-01", 90.0),
        _c("Delhi", "pm10", "2026-06-01", 250.0),
        _c("Delhi", "no2", "2026-06-01", 80.0),
        _c("Delhi", "so2", "2026-06-01", 40.0),
    ]
    rows = storage.assemble_daily_rows(recs)
    assert len(rows) == 1
    row = rows[0]
    assert row["city"] == "Delhi"
    assert row["date"] == "2026-06-01"
    assert row["pm25"] == 90.0 and row["pm10"] == 250.0
    # §7 expectations — precomputed by the tested engine.
    assert row["aqi_naqi"] == 200 and row["naqi_category"] == "Moderate"
    assert row["aqi_us"] == 175 and row["us_category"] == "Unhealthy"
    assert row["eu_band"] == "Very Poor"
    assert row["source"] == "openaq"


def test_assemble_daily_row_naqi_invalid_when_too_few_pollutants():
    rows = storage.assemble_daily_rows([_c("Delhi", "pm25", "2026-06-01", 90.0)])
    assert rows[0]["aqi_naqi"] is None       # NAQI needs >=3 pollutants
    assert rows[0]["aqi_us"] == 175           # US still computes


def test_assemble_daily_rows_merges_weather():
    recs = [
        _c("Delhi", "pm25", "2026-06-01", 90.0),
        _c("Delhi", "pm10", "2026-06-01", 250.0),
        _c("Delhi", "no2", "2026-06-01", 80.0),
    ]
    weather = {("Delhi", "2026-06-01"): WeatherRecord(
        source="open-meteo", lat=28.6, lon=77.2, datetime_utc="2026-06-01T00:00:00Z",
        averaging="1d", temp_c=38.5, rh_pct=40, precip_mm=0.0, wind_speed_ms=2.5,
        temp_min_c=29.0, temp_max_c=44.0)}
    rows = storage.assemble_daily_rows(recs, weather_by_city_date=weather)
    assert rows[0]["temp_c"] == 38.5
    assert rows[0]["wind_ms"] == 2.5
    assert rows[0]["temp_max_c"] == 44.0


def test_assemble_daily_rows_sorted_by_city_date():
    recs = [
        _c("Mumbai", "pm25", "2026-06-02", 40.0),
        _c("Delhi", "pm25", "2026-06-01", 90.0),
        _c("Delhi", "pm25", "2026-06-02", 95.0),
    ]
    rows = storage.assemble_daily_rows(recs)
    assert [(r["city"], r["date"]) for r in rows] == [
        ("Delhi", "2026-06-01"), ("Delhi", "2026-06-02"), ("Mumbai", "2026-06-02")]


def test_write_parquet_merges_idempotently(tmp_path):
    import polars as pl
    # Initial write: dates 1 & 2.
    rows1 = storage.assemble_daily_rows([
        _c("Delhi", "pm25", "2026-06-01", 50.0), _c("Delhi", "no2", "2026-06-01", 30.0),
        _c("Delhi", "pm25", "2026-06-02", 60.0), _c("Delhi", "no2", "2026-06-02", 30.0),
    ])
    storage.write_parquet_per_city(rows1, tmp_path, merge_keys=["date"])
    # Delta write: date 2 (updated value) & new date 3.
    rows2 = storage.assemble_daily_rows([
        _c("Delhi", "pm25", "2026-06-02", 999.0), _c("Delhi", "no2", "2026-06-02", 30.0),
        _c("Delhi", "pm25", "2026-06-03", 70.0), _c("Delhi", "no2", "2026-06-03", 30.0),
    ])
    storage.write_parquet_per_city(rows2, tmp_path, merge_keys=["date"])

    df = pl.read_parquet(tmp_path / "delhi.parquet").sort("date")
    assert df["date"].to_list() == ["2026-06-01", "2026-06-02", "2026-06-03"]   # no dup, no loss
    assert df.filter(pl.col("date") == "2026-06-02")["pm25"].item() == 999.0    # delta won


def test_write_parquet_recent_prunes_old(tmp_path):
    import datetime as dt
    import polars as pl
    today = dt.date.today()
    old = (today - dt.timedelta(days=200)).isoformat()
    fresh = (today - dt.timedelta(days=2)).isoformat()
    rows = [
        {"city": "Delhi", "datetime_utc": f"{old}T05:00:00Z", "pm25": 10.0},
        {"city": "Delhi", "datetime_utc": f"{fresh}T05:00:00Z", "pm25": 20.0},
    ]
    storage.write_parquet_per_city(rows, tmp_path, merge_keys=["datetime_utc"],
                                   keep_days=90, date_col="datetime_utc")
    df = pl.read_parquet(tmp_path / "delhi.parquet")
    assert df.height == 1                      # the 200-day-old row was pruned
    assert df["datetime_utc"].item().startswith(fresh)


def test_write_parquet_handles_late_appearing_column(tmp_path):
    import polars as pl
    # A column null for the first 100+ rows then a float later must not break schema inference.
    rows = [{"city": "X", "date": f"2026-01-{(i % 28) + 1:02d}-{i}", "co": None} for i in range(110)]
    rows.append({"city": "X", "date": "2026-05-01", "co": 989.97})
    storage.write_parquet_per_city(rows, tmp_path, merge_keys=["date"])
    df = pl.read_parquet(tmp_path / "x.parquet")
    assert df.filter(pl.col("date") == "2026-05-01")["co"].item() == 989.97


def test_live_snapshot_shape():
    recs = [
        _c("Delhi", "pm25", "2026-06-11", 90.0, source="cpcb"),
        _c("Delhi", "pm10", "2026-06-11", 250.0, source="cpcb"),
        _c("Delhi", "no2", "2026-06-11", 80.0, source="cpcb"),
    ]
    snap = storage.live_snapshot("Delhi", recs, updated_utc="2026-06-11T12:30:00Z")
    assert snap["city"] == "Delhi"
    assert snap["source"] == "cpcb"
    assert snap["updated_utc"] == "2026-06-11T12:30:00Z"
    assert snap["pollutants"]["pm25"]["value"] == 90.0
    # per-pollutant sub-index for the default standard (NAQI) is included
    assert snap["pollutants"]["pm25"]["naqi_subindex"] == 200
    assert snap["aqi"]["naqi"]["index"] == 200
    assert snap["aqi"]["us"]["index"] == 175
    assert snap["aqi"]["eu"]["band"] == "Very Poor"
