"""Orchestrates a full, idempotent data refresh.

Pipeline: fetch (ingest/*) -> compute AQI (aqi/*) -> aggregate & reconcile (transform/*)
-> write data/live (JSON), data/history + data/recent (Parquet), data/meta.

Modes:
    python run.py backfill   # full daily history + recent hourly + live + meta
    python run.py daily      # recent daily delta + recent hourly + live + meta
    python run.py hourly     # live snapshot + current weather only

Re-running reproduces the same outputs; gaps backfill on the next run. Bound the work with
--cities / --max-per-city / --from / --to (used for sampling and CI shards).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os

import build
from transform import reconcile, storage


def _load_env():
    env_path = build.ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _today_ist() -> str:
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    return dt.datetime.now(tz=ist).strftime("%Y-%m-%d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backfill", "daily", "hourly"])
    ap.add_argument("--cities", nargs="*", default=None, help="limit to these cities")
    ap.add_argument("--max-per-city", type=int, default=None)
    ap.add_argument("--from", dest="date_from", default=None)
    ap.add_argument("--to", dest="date_to", default=None)
    ap.add_argument("--sensors", choices=["first", "all"], default="first")
    ap.add_argument("--recent-days", type=int, default=90)
    args = ap.parse_args()

    _load_env()
    oa_key = os.environ.get("OPENAQ_API_KEY", "")
    dg_key = os.environ.get("DATA_GOV_IN_KEY", "")
    today = _today_ist()
    yesterday = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()

    default_from = {"backfill": "2016-01-01", "daily": yesterday, "hourly": today}[args.mode]
    date_from = args.date_from or default_from
    date_to = args.date_to or yesterday

    print(f"[run] mode={args.mode} cities={args.cities or 'ALL'} window={date_from}..{date_to}")

    print("[run] discovering stations…")
    stations, mapping, unmapped = build.discover(oa_key)
    sel = build.select_stations(stations, mapping, cities=set(args.cities) if args.cities else None,
                                max_per_city=args.max_per_city)
    centroids = build.city_centroids(sel, mapping)
    print(f"[run] {len(sel)} stations across {len(centroids)} cities ({len(unmapped)} unmapped)")

    # ---- History (daily) + recent (hourly) ----
    daily_rows, hourly_rows = [], []
    if args.mode in ("backfill", "daily"):
        print("[run] fetching daily history…")
        city_daily = build.fetch_city_aq(oa_key, sel, mapping, date_from=date_from,
                                          date_to=date_to, period="days", sensors=args.sensors)
        # today = CPCB (if available), history = OpenAQ
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
        wx_daily = build.fetch_weather_daily(centroids, start_date=date_from, end_date=today)
        daily_rows = storage.assemble_daily_rows(city_daily, weather_by_city_date=wx_daily)

        print("[run] fetching recent hourly…")
        recent_from = (dt.date.fromisoformat(today) - dt.timedelta(days=args.recent_days)).isoformat()
        city_hourly = build.fetch_city_aq(oa_key, sel, mapping, date_from=recent_from,
                                          date_to=today, period="hours", sensors=args.sensors)
        hourly_rows = storage.assemble_hourly_rows(city_hourly)

    # ---- Live snapshot (today) ----
    live_count = 0
    if dg_key:
        try:
            live = build.fetch_live_cpcb(dg_key, mapping)
            wx_now = build.fetch_weather_current(centroids)
            by_city = {}
            for r in live:
                if args.cities and r.city not in set(args.cities):
                    continue
                by_city.setdefault(r.city, []).append(r)
            for city, recs in by_city.items():
                snap = storage.live_snapshot(city, recs, updated_utc=recs[0].datetime_utc,
                                             weather=wx_now.get(city))
                storage.write_live_json(snap, build.DATA / "live")
                live_count += 1
        except Exception as e:
            print(f"[run] live snapshot skipped ({type(e).__name__}: data.gov.in down)")

    # ---- Write parquet + meta (idempotent upsert; recent tier pruned to the window) ----
    if daily_rows:
        storage.write_parquet_per_city(daily_rows, build.DATA / "history", merge_keys=["date"])
    if hourly_rows:
        storage.write_parquet_per_city(hourly_rows, build.DATA / "recent",
                                       merge_keys=["datetime_utc"], keep_days=args.recent_days,
                                       date_col="datetime_utc")

    # Station map is cheap + always current; city_list/coverage derive from the daily tier,
    # so only (re)write them when this run actually built daily rows (don't clobber in hourly mode).
    storage.write_json(mapping, build.META / "station_city_map.json")
    storage.write_json({"unmapped_station_ids": unmapped}, build.META / "unmapped_stations.json")
    if daily_rows:
        storage.write_json({"generated_today": today,
                            "cities": sorted({r["city"] for r in daily_rows})},
                           build.META / "city_list.json")
        storage.write_json(build.build_coverage(daily_rows), build.META / "coverage.json")
        storage.write_json(build.build_cities_index(daily_rows, centroids),
                           build.META / "cities.json")

    n_cities = len({r["city"] for r in daily_rows})
    print(f"[run] done. daily_rows={len(daily_rows)} hourly_rows={len(hourly_rows)} "
          f"live_cities={live_count} daily_cities={n_cities}")


if __name__ == "__main__":
    main()
