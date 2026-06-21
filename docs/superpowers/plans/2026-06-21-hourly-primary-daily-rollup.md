# Hourly-primary daily rollup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the routine daily refresh hourly-primary — fetch only OpenAQ `/hours`, compute the daily number ourselves from the hourly tier, derive freshness from the data we actually hold, and make failure logs self-describing.

**Architecture:** In `daily` mode, `run.py` stops calling OpenAQ `/days` (it lags and 422s on equal-date windows). It fetches the hourly tier, then `aggregate.rollup_hourly_to_daily` rolls each city's hours up to a per-city daily mean (matching OpenAQ's `summary.avg`) with a per-pollutant coverage threshold. The daily tier then advances on its own, so `city_list.json` freshness and the city list are rebuilt from the on-disk daily tier every run (no `daily_rows` gate). `backfill` mode keeps `/days` for historical loads. Logging gains status codes + per-tier summaries.

**Tech Stack:** Python 3.13, polars, httpx, pytest, ruff. Tests live alongside source (e.g. `pipeline/transform/test_aggregate.py`). Run from `pipeline/` with the venv: `pipeline/.venv/bin/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-21-hourly-primary-daily-rollup-design.md`
**Branch:** `fix/hourly-primary-daily-rollup` (already created)

---

## File structure

- `pipeline/transform/aggregate.py` — **add** `rollup_hourly_to_daily()`. Pure, unit-tested.
- `pipeline/transform/test_aggregate.py` — **add** rollup tests.
- `pipeline/build.py` — **add** `_http_status()` helper; **modify** `fetch_city_aq()` for status-aware skip logging + per-tier summary; **add** `latest_daily_date()`.
- `pipeline/test_build.py` — **add** logging-summary + `latest_daily_date` tests.
- `pipeline/ingest/http.py` — **modify** the final `RuntimeError` to carry the HTTP status.
- `pipeline/ingest/test_http.py` — **add** a test that the RuntimeError message includes the status.
- `pipeline/run.py` — **modify** `daily` mode to be hourly-primary; **modify** the meta write to be ungated.
- `pipeline/scripts/validate_rollup.py` — **create**: confidence check comparing the hourly rollup against the stored `/days`-derived daily tier on overlapping days.
- `scripts/smoke.mjs` — **modify** comment only.

---

## Task 1: `rollup_hourly_to_daily` in aggregate.py

**Files:**
- Modify: `pipeline/transform/aggregate.py`
- Test: `pipeline/transform/test_aggregate.py`

- [ ] **Step 1: Write the failing tests**

Append to `pipeline/transform/test_aggregate.py`:

```python
from transform.aggregate import CityPollutantRecord


def _hourly(city, param, dt_utc, value, *, n_stations=2, cov=100.0):
    return CityPollutantRecord(
        city=city, parameter=param, datetime_utc=dt_utc, averaging="1h",
        value=value, unit="µg/m³", n_stations=n_stations, coverage_pct=cov,
        source="openaq")


def test_rollup_means_full_day_above_threshold():
    # 18 hours of PM2.5 on the same IST day -> one daily mean record.
    recs = [_hourly("Pune", "pm25", f"2026-06-19T{h:02d}:00:00Z", 50.0 + h)
            for h in range(18)]
    out = agg.rollup_hourly_to_daily(recs, min_hours=18)
    assert len(out) == 1
    r = out[0]
    assert r.averaging == "1d"
    assert r.city == "Pune" and r.parameter == "pm25"
    assert r.value == sum(50.0 + h for h in range(18)) / 18
    assert r.n_stations == 2


def test_rollup_skips_pollutant_below_threshold():
    # Only 5 hours -> below 18 -> omitted, not fabricated.
    recs = [_hourly("Pune", "no2", f"2026-06-19T{h:02d}:00:00Z", 20.0)
            for h in range(5)]
    assert agg.rollup_hourly_to_daily(recs, min_hours=18) == []


def test_rollup_is_per_pollutant():
    # pm25 has 18 hours (kept); co has 3 (dropped) -> only pm25 survives.
    recs = [_hourly("Pune", "pm25", f"2026-06-19T{h:02d}:00:00Z", 40.0) for h in range(18)]
    recs += [_hourly("Pune", "co", f"2026-06-19T{h:02d}:00:00Z", 1.0) for h in range(3)]
    out = agg.rollup_hourly_to_daily(recs, min_hours=18)
    assert {r.parameter for r in out} == {"pm25"}


def test_rollup_buckets_by_ist_local_day():
    # 2026-06-19T20:00Z is 2026-06-20T01:30 IST -> belongs to the 06-20 bucket, keyed local.
    recs = [_hourly("Pune", "pm25", f"2026-06-19T{h:02d}:00:00Z", 10.0) for h in range(20)]
    # Hours 18,19 (18:30Z+) cross into IST 06-20; 0..17 stay in IST 06-19 with the +5:30 shift.
    out = agg.rollup_hourly_to_daily(recs, min_hours=1)
    dates = sorted(r.datetime_utc for r in out)
    assert dates[0] == "2026-06-19T00:00:00Z"
    assert dates[-1].startswith("2026-06-20")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline && .venv/bin/python -m pytest transform/test_aggregate.py -k rollup -v`
Expected: FAIL with `AttributeError: module 'transform.aggregate' has no attribute 'rollup_hourly_to_daily'`

- [ ] **Step 3: Implement `rollup_hourly_to_daily`**

Add to `pipeline/transform/aggregate.py` (after `aggregate_to_city`):

```python
def rollup_hourly_to_daily(
    hourly: list[CityPollutantRecord], *, min_hours: int = 18, tz_offset_hours: float = 5.5,
) -> list[CityPollutantRecord]:
    """Roll city-hour concentration records up to city-day records by arithmetic MEAN.

    This matches OpenAQ's /days `summary.avg` (the value our historical tier was built on), so
    self-computed days are methodologically identical to the old /days-derived days. Median-across-
    stations is already applied per hour upstream (aggregate_to_city), so this only collapses the
    time axis. A (city, pollutant, local-day) value is emitted ONLY if at least `min_hours` valid
    hours are present; sparser days are omitted, never fabricated. Hours are bucketed by LOCAL
    calendar day (IST, +5:30) to match the daily tier's local-date keying.
    """
    import datetime as _dt

    tz = _dt.timezone(_dt.timedelta(hours=tz_offset_hours))
    groups: dict[tuple, list[CityPollutantRecord]] = defaultdict(list)
    for r in hourly:
        if r.value is None:
            continue
        try:
            ts = _dt.datetime.fromisoformat(r.datetime_utc.replace("Z", "+00:00"))
        except ValueError:
            continue
        local_date = ts.astimezone(tz).date().isoformat()
        groups[(r.city, r.parameter, local_date)].append(r)

    out: list[CityPollutantRecord] = []
    for (city, param, local_date), rs in groups.items():
        if len(rs) < min_hours:
            continue
        values = [r.value for r in rs]
        covs = [r.coverage_pct for r in rs if r.coverage_pct is not None]
        out.append(CityPollutantRecord(
            city=city, parameter=param, datetime_utc=f"{local_date}T00:00:00Z",
            averaging="1d", value=sum(values) / len(values), unit=rs[0].unit,
            n_stations=max(r.n_stations for r in rs),
            coverage_pct=(sum(covs) / len(covs)) if covs else None,
            source=rs[0].source or "openaq",
        ))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && .venv/bin/python -m pytest transform/test_aggregate.py -k rollup -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/transform/aggregate.py pipeline/transform/test_aggregate.py
git commit -m "feat(pipeline): hourly->daily rollup (mean, per-pollutant coverage, IST bucketing)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Status-aware logging + per-tier summary

**Files:**
- Modify: `pipeline/ingest/http.py:122`
- Modify: `pipeline/build.py` (add `_http_status`; rewrite `fetch_city_aq` loop)
- Test: `pipeline/ingest/test_http.py`, `pipeline/test_build.py`

- [ ] **Step 1: Write the failing tests**

Append to `pipeline/ingest/test_http.py`:

```python
def test_runtime_error_includes_status(monkeypatch):
    import httpx
    from ingest import http

    class _Resp:
        status_code = 503
        headers = {}
        request = None
        def json(self): return {}
    def _boom(*a, **k):
        return _Resp()
    monkeypatch.setattr(http.httpx, "get", _boom)
    monkeypatch.setattr(http.time, "sleep", lambda *a, **k: None)
    try:
        http.get_json("https://x/y", retries=2, use_cache=False)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "503" in str(e)
```

Append to `pipeline/test_build.py`:

```python
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
```

(If `Station`/`Sensor` constructor args differ, match `pipeline/ingest/records.py`; the existing `pipeline/test_build.py` already builds Stations — copy its pattern.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline && .venv/bin/python -m pytest ingest/test_http.py::test_runtime_error_includes_status test_build.py -k "http_status or summary" -v`
Expected: FAIL (`_http_status` missing; summary line absent; RuntimeError lacks "503")

- [ ] **Step 3a: Add status to the http.py RuntimeError**

In `pipeline/ingest/http.py`, replace line 122:

```python
    raise RuntimeError(f"GET failed after {retries} attempts: {url}") from last_err
```

with:

```python
    status = (last_err.response.status_code
              if isinstance(last_err, httpx.HTTPStatusError) and last_err.response is not None
              else None)
    label = f"HTTP {status}" if status else type(last_err).__name__
    raise RuntimeError(f"GET failed after {retries} attempts ({label}): {url}") from last_err
```

- [ ] **Step 3b: Add `_http_status` and rewrite the fetch loop in build.py**

In `pipeline/build.py`, add near the top (after imports):

```python
def _http_status(e: Exception) -> str:
    """Human-readable status for a fetch failure: 'HTTP 422' when available, else the type."""
    import httpx
    err = e
    cause = getattr(e, "__cause__", None)
    if isinstance(cause, httpx.HTTPStatusError):
        err = cause
    if isinstance(err, httpx.HTTPStatusError) and err.response is not None:
        return f"HTTP {err.response.status_code}"
    return type(e).__name__
```

Replace the body of `fetch_city_aq` (currently lines ~124-138) with:

```python
    raw: list[AQRecord] = []
    n_ok = n_empty = n_failed = 0
    by_status: dict[str, int] = defaultdict(int)
    for s in stations:
        city = mapping.get(s.station_id)
        for sensor_id, _param in _sensors_for(s, sensors):
            try:
                recs = openaq.fetch_sensor_history(
                    api_key, sensor_id, date_from=date_from, date_to=date_to, period=period,
                    station_id=s.station_id, station_name=s.name, city=city,
                    state=None, lat=s.lat, lon=s.lon)
                raw += recs
                n_ok += 1 if recs else 0
                n_empty += 0 if recs else 1
            except Exception as e:
                # One flaky sensor must not abort the build (self-healing: it backfills next run).
                n_failed += 1
                status = _http_status(e)
                by_status[status] += 1
                print(f"[build] skip sensor {sensor_id} ({period}) {city} "
                      f"{date_from}..{date_to}: {status}", flush=True)
    detail = " ".join(f"{k}×{v}" for k, v in sorted(by_status.items()))
    print(f"[build] {period}: {n_ok + n_empty + n_failed} sensors -> "
          f"{n_ok} ok, {n_empty} empty, {n_failed} failed"
          f"{(' (' + detail + ')') if detail else ''}", flush=True)
    return agg.aggregate_to_city(raw, mapping, min_coverage=min_coverage)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && .venv/bin/python -m pytest ingest/test_http.py::test_runtime_error_includes_status test_build.py -k "http_status or summary" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/ingest/http.py pipeline/ingest/test_http.py pipeline/build.py pipeline/test_build.py
git commit -m "feat(pipeline): status-aware fetch logging + per-tier summary

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `latest_daily_date` helper (freshness source of truth)

**Files:**
- Modify: `pipeline/build.py`
- Test: `pipeline/test_build.py`

- [ ] **Step 1: Write the failing test**

Append to `pipeline/test_build.py`:

```python
def test_latest_daily_date_picks_max():
    import build
    rows = [{"city": "A", "date": "2026-06-14"}, {"city": "B", "date": "2026-06-20"},
            {"city": "A", "date": "2026-06-15"}]
    assert build.latest_daily_date(rows) == "2026-06-20"


def test_latest_daily_date_empty():
    import build
    assert build.latest_daily_date([]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && .venv/bin/python -m pytest test_build.py -k latest_daily_date -v`
Expected: FAIL (`latest_daily_date` missing)

- [ ] **Step 3: Implement `latest_daily_date`**

Add to `pipeline/build.py`:

```python
def latest_daily_date(all_daily: list[dict]) -> str | None:
    """The freshest calendar date present in the daily tier — the 'data through' freshness
    signal. None when the tier is empty."""
    dates = [r["date"] for r in all_daily if r.get("date")]
    return max(dates) if dates else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline && .venv/bin/python -m pytest test_build.py -k latest_daily_date -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/build.py pipeline/test_build.py
git commit -m "feat(pipeline): latest_daily_date helper for data-through freshness

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Wire `daily` mode to the hourly rollup

**Files:**
- Modify: `pipeline/run.py:25` (import), `pipeline/run.py:171-201` (fetch block)

- [ ] **Step 1: Add the aggregate import**

In `pipeline/run.py`, change line 25:

```python
from transform import reconcile, storage
```

to:

```python
from transform import aggregate, reconcile, storage
```

- [ ] **Step 2: Replace the History/recent fetch block**

Replace `pipeline/run.py` lines 171-201 (from `# ---- History (daily) + recent (hourly) ----` through `hourly_rows = storage.assemble_hourly_rows(city_hourly)`) with:

```python
    # ---- Recent hourly tier + daily rollup ----
    # Daily mode is HOURLY-PRIMARY: OpenAQ /days lags days behind and 422s on equal-date windows,
    # so we fetch only /hours and compute the daily value ourselves (mean over the day's hours,
    # matching OpenAQ's summary.avg). backfill mode still uses /days for multi-year history.
    # See docs/superpowers/specs/2026-06-21-hourly-primary-daily-rollup-design.md
    daily_rows, hourly_rows = [], []
    if args.mode in ("backfill", "daily"):
        recent_from = (dt.date.fromisoformat(today) - dt.timedelta(days=args.recent_days)).isoformat()
        print(f"[run] fetching recent hourly (last {args.recent_days}d)…")
        city_hourly = build.fetch_city_aq(oa_key, sel, mapping, date_from=recent_from,
                                          date_to=today, period="hours", sensors=args.sensors)
        hourly_rows = storage.assemble_hourly_rows(city_hourly)

        if args.mode == "backfill":
            print("[run] fetching daily history (/days)…")
            city_daily = build.fetch_city_aq(oa_key, sel, mapping, date_from=date_from,
                                             date_to=date_to, period="days", sensors=args.sensors)
            wx_from = date_from
        else:
            min_hours = int(os.environ.get("AIRATLAS_MIN_DAILY_HOURS", "18"))
            city_daily = aggregate.rollup_hourly_to_daily(city_hourly, min_hours=min_hours)
            print(f"[run] rolled up {len(city_daily)} city-pollutant-days from hourly "
                  f"(min_hours={min_hours})")
            wx_from = recent_from

        # today = CPCB (if available), history = OpenAQ (rollup in daily mode)
        today_cpcb = []
        if dg_key:
            try:
                today_cpcb = [r for r in build.fetch_live_cpcb(dg_key, mapping)
                              if not args.cities or r.city in set(args.cities)]
                print(f"[run] CPCB live: {len(today_cpcb)} city-pollutant records")
            except Exception as e:
                print(f"[run] CPCB live unavailable ({type(e).__name__}); history-only today")
        city_daily = reconcile.reconcile_daily(today_cpcb=today_cpcb,
                                                history_openaq=city_daily, today=today)
        print("[run] fetching daily weather…")
        # Open-Meteo's archive only allows end_date up to YESTERDAY (today -> 400).
        wx_daily = build.fetch_weather_daily(centroids, start_date=wx_from, end_date=yesterday)
        daily_rows = storage.assemble_daily_rows(city_daily, weather_by_city_date=wx_daily)
```

- [ ] **Step 3: Bump the daily recent-days default to cover a full IST day**

In `pipeline/run.py`, the `--recent-days` argument (line ~87) `default=1` → `default=2` (an IST calendar day spans two UTC days, so ≥2 days of hourly are needed for one complete local day; cheap because `/hours` returns the whole window in one call per sensor):

```python
    ap.add_argument("--recent-days", type=int, default=2,
```

(Leave the help text; optionally append "≥2 so a full IST day can be rolled up.")

- [ ] **Step 4: Verify the full suite still passes (no regressions)**

Run: `cd pipeline && .venv/bin/python -m pytest -q`
Expected: PASS (all prior tests + the new ones; ~105 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): daily mode is hourly-primary (rollup), drops /days fetch

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Ungate the meta/freshness write

**Files:**
- Modify: `pipeline/run.py:236-254` (the meta-write block)

- [ ] **Step 1: Replace the gated meta write**

Replace `pipeline/run.py` lines 240-254 (the `if daily_rows:` block that rebuilds `city_list.json`/`coverage.json`/`cities.json`) with an ungated rebuild from the on-disk daily tier:

```python
    # Rebuild meta from the FULL on-disk daily tier EVERY run (not gated on this run's rows), so
    # freshness + the city list reflect what we actually hold even when no new daily rows landed.
    # Freshness = "data through" = the latest date present in the daily tier (NOT the run date).
    all_daily = storage.read_all_daily(build.DATA / "history")
    if all_daily:
        prior_path = build.META / "cities.json"
        prior_index = json.loads(prior_path.read_text()) if prior_path.exists() else []
        all_centroids = build.merge_centroids(centroids, prior_index)
        freshness = build.latest_daily_date(all_daily)
        storage.write_json({"generated_today": freshness,
                            "cities": sorted({r["city"] for r in all_daily})},
                           build.META / "city_list.json")
        storage.write_json(build.build_coverage(all_daily), build.META / "coverage.json")
        storage.write_json(build.build_cities_index(all_daily, all_centroids),
                           build.META / "cities.json")
        print(f"[run] meta rebuilt: generated_today={freshness}, "
              f"cities={len({r['city'] for r in all_daily})}")
```

Note: `generated_today` keeps its key name for low blast radius (only `scripts/smoke.mjs` reads it; the frontend loads but does not display it). Its meaning is now "data through", documented in the comment above.

- [ ] **Step 2: Verify the suite still passes**

Run: `cd pipeline && .venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 3: Lint**

Run: `cd pipeline && .venv/bin/python -m ruff check .`
Expected: no errors (fix any line-length>100 / import issues inline).

- [ ] **Step 4: Commit**

```bash
git add pipeline/run.py
git commit -m "fix(pipeline): freshness = data-through date, rebuilt every run

generated_today now reflects the latest date in the daily tier and is
written even when a run adds no new rows, so deploy/uptime smoke checks
stop failing on naturally-lagging source data.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Rollup validation script + smoke comment

**Files:**
- Create: `pipeline/scripts/validate_rollup.py`
- Modify: `scripts/smoke.mjs:12` (comment only)

- [ ] **Step 1: Create the validation script**

Create `pipeline/scripts/validate_rollup.py`:

```python
"""Confidence check: does the hourly->daily rollup reproduce the stored /days-derived daily
tier on overlapping days? Run before trusting the cutover.

Usage: pipeline/.venv/bin/python scripts/validate_rollup.py --data-dir /path/to/data
Reads <data-dir>/recent/*.parquet (hourly, wide) and <data-dir>/history/*.parquet (daily, wide),
re-derives the daily mean per (city, IST-day, pollutant) from the hourly rows, and compares to the
stored daily value. Prints match rate within tolerance.
"""
import argparse
import datetime as dt
import glob
import os

import polars as pl

POLLUTANTS = ["pm25", "pm10", "no2", "so2", "o3", "co", "nh3"]
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--min-hours", type=int, default=18)
    ap.add_argument("--tol", type=float, default=0.10, help="relative tolerance")
    args = ap.parse_args()

    recent = pl.read_parquet(f"{args.data_dir}/recent/*.parquet")
    history = pl.read_parquet(f"{args.data_dir}/history/*.parquet")

    # IST local date from the UTC instant.
    recent = recent.with_columns(
        (pl.col("datetime_utc").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%SZ", strict=False)
         .dt.replace_time_zone("UTC").dt.convert_time_zone("Asia/Kolkata")
         .dt.date().cast(pl.Utf8)).alias("ist_date"))

    checked = matched = 0
    for p in POLLUTANTS:
        if p not in recent.columns or p not in history.columns:
            continue
        roll = (recent.filter(pl.col(p).is_not_null())
                .group_by(["city", "ist_date"])
                .agg(pl.col(p).mean().alias("roll"), pl.len().alias("hours"))
                .filter(pl.col("hours") >= args.min_hours))
        stored = history.select(["city", "date", p]).rename({"date": "ist_date", p: "stored"})
        j = roll.join(stored, on=["city", "ist_date"], how="inner").filter(
            pl.col("stored").is_not_null())
        if j.height == 0:
            continue
        j = j.with_columns(
            ((pl.col("roll") - pl.col("stored")).abs()
             / pl.max_horizontal(pl.col("stored").abs(), pl.lit(1.0))).alias("rel"))
        ok = j.filter(pl.col("rel") <= args.tol).height
        checked += j.height
        matched += ok
        print(f"  {p:5}: {ok}/{j.height} within {args.tol:.0%} "
              f"(median rel={j['rel'].median():.3f})")

    if checked:
        print(f"\nOVERALL: {matched}/{checked} ({matched / checked:.1%}) within tolerance")
    else:
        print("\nNo overlapping (city, day, pollutant) rows to compare.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the validation against published data**

```bash
cd "/Users/sarveshtewari/claude/AQI Dashboard"
rm -rf /tmp/aqi-databranch && git archive origin/data data | tar -x -C /tmp -f - 2>/dev/null || (mkdir -p /tmp/aqi-databranch && git archive origin/data data | tar -x -C /tmp/aqi-databranch)
cd pipeline && .venv/bin/python scripts/validate_rollup.py --data-dir /tmp/data 2>/dev/null || .venv/bin/python scripts/validate_rollup.py --data-dir /tmp/aqi-databranch/data
```
Expected: a per-pollutant match table and an OVERALL line. **Checkpoint:** if OVERALL is high (e.g. ≥90% within 10%) the rollup faithfully reproduces `/days`; if low, STOP and revisit the aggregation order before cutover.

- [ ] **Step 3: Update the smoke comment**

In `scripts/smoke.mjs` line 12, update the comment to reflect the new meaning:

```javascript
const STALE_AFTER_DAYS = 4; // generated_today = "data through" (latest daily date); data lags ~1-2d by nature, older than this means a stalled pipeline.
```

- [ ] **Step 4: Commit**

```bash
git add pipeline/scripts/validate_rollup.py scripts/smoke.mjs
git commit -m "test(pipeline): rollup-vs-/days validation script + smoke comment

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Live verification

**Files:** none (verification only)

- [ ] **Step 1: Scoped local daily run**

```bash
cd pipeline && .venv/bin/python run.py daily --cities Pune Mumbai --sensors first
```
Expected output includes: `[build] hours: N sensors -> ...`, `[run] rolled up M city-pollutant-days from hourly`, and `[run] meta rebuilt: generated_today=2026-06-20` (or the latest available local day). Confirm no `/days` fetch line appears.

- [ ] **Step 2: Inspect the written meta**

```bash
cd pipeline && .venv/bin/python -c "import json; d=json.load(open('../data/meta/city_list.json')); print('generated_today=', d['generated_today'], 'cities=', len(d['cities']))"
```
Expected: `generated_today` is yesterday's IST date (advanced past 06-16), cities preserved.

- [ ] **Step 3: Push the branch and open a PR (CI runs ruff + pytest + web build)**

```bash
cd "/Users/sarveshtewari/claude/AQI Dashboard"
git push -u origin fix/hourly-primary-daily-rollup
gh pr create --fill --title "Hourly-primary pipeline + self-computed daily rollup"
```

- [ ] **Step 4: After merge, trigger and watch the scheduled daily**

```bash
gh workflow run refresh-daily.yml -f mode=daily -f sensors=first
```
Expected: completes well under the 330-min cap, `generated_today` advances on the live site, and deploy + uptime go green. Verify:
```bash
python3 -c "import urllib.request,json; print(json.load(urllib.request.urlopen('https://sarvesh-tewari.github.io/AirAtlas/data/meta/city_list.json'))['generated_today'])"
```

---

## Self-review

- **Spec coverage:** hourly-primary fetch (Task 4) ✓; self-computed daily rollup with mean + 18h per-pollutant threshold + IST bucketing (Task 1) ✓; freshness = data-through, ungated, cities preserved (Tasks 3, 5) ✓; logging status + summary (Task 2) ✓; validation gate vs /days (Task 6) ✓; smoke comment (Task 6) ✓; backfill keeps /days (Task 4) ✓; #8 deferred (no max-window work present) ✓.
- **Type consistency:** `rollup_hourly_to_daily(hourly, *, min_hours, tz_offset_hours)`, `latest_daily_date(all_daily) -> str|None`, `_http_status(e) -> str` used consistently across tasks and run.py wiring.
- **No placeholders:** every code step shows full code; commands have expected output.
- **Risk note:** Task 6 Step 2 is a hard checkpoint — a low match rate blocks cutover.
