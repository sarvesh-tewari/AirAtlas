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
import json
import os

import build
import plan
from transform import reconcile, storage


def _load_env():
    env_path = build.ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                os.environ.setdefault(k.strip(), v)


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
    ap.add_argument("--next-batch", type=int, default=None,
                    help="backfill the next N not-yet-published cities (incremental drip); "
                         "self-selects from discovered universe minus data/meta/city_list.json")
    args = ap.parse_args()

    _load_env()
    # .strip() guards against stray whitespace/newlines in the stored secret (an errant
    # leading space makes httpx reject the X-API-Key header).
    oa_key = os.environ.get("OPENAQ_API_KEY", "").strip()
    dg_key = os.environ.get("DATA_GOV_IN_KEY", "").strip()
    if not oa_key:
        # No OpenAQ key (e.g. CI before secrets are configured) — exit cleanly, not as a failure.
        print("[run] OPENAQ_API_KEY not set — nothing to do. Add the Actions secret to enable refreshes.")
        return
    today = _today_ist()
    yesterday = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()

    default_from = {"backfill": "2016-01-01", "daily": yesterday, "hourly": today}[args.mode]
    date_from = args.date_from or default_from
    date_to = args.date_to or yesterday

    print(f"[run] mode={args.mode} cities={args.cities or 'ALL'} window={date_from}..{date_to}")

    print("[run] discovering stations…")
    stations, mapping, unmapped = build.discover(oa_key)

    # Incremental drip: self-select the next N cities not yet processed (complete-or-absent).
    # "Processed" = published (city_list) OR already attempted — the latter so mapped-but-empty
    # cities (no OpenAQ history) aren't re-selected forever, which would stall the drip.
    if args.next_batch:
        clp = build.META / "city_list.json"
        done = set(json.loads(clp.read_text()).get("cities", [])) if clp.exists() else set()
        ap_path = build.META / "backfill_attempted.json"
        if ap_path.exists():
            done |= set(json.loads(ap_path.read_text()).get("cities", []))
        args.cities = plan.next_batch(set(mapping.values()), done, args.next_batch)
        if not args.cities:
            print("[run] incremental backfill complete — no unpublished cities remain.")
            return
        print(f"[run] drip batch ({len(args.cities)}): {' '.join(args.cities)}")

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
        except Exception as e:
            live, wx_now = [], {}
            print(f"[run] CPCB live fetch failed ({type(e).__name__}); keeping last-good live data")
        by_city = {}
        for r in live:
            if args.cities and r.city not in set(args.cities):
                continue
            by_city.setdefault(r.city, []).append(r)
        for city, recs in by_city.items():
            # Isolate per city so one bad city can't suppress the rest.
            try:
                snap = storage.live_snapshot(city, recs, updated_utc=recs[0].datetime_utc,
                                             weather=wx_now.get(city))
                storage.write_live_json(snap, build.DATA / "live")
                live_count += 1
            except Exception as e:
                print(f"[run] live snapshot skipped for {city}: {type(e).__name__}: {e}")

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
        # Rebuild meta from the FULL on-disk daily tier (all cities, all history) — NOT just this
        # run's rows. This makes incremental/subset backfills accumulate cities instead of
        # clobbering the selector, and makes coverage reflect full history rather than the delta
        # window. Centroids for cities outside this run are recovered from the prior index.
        all_daily = storage.read_all_daily(build.DATA / "history")
        prior_path = build.META / "cities.json"
        prior_index = json.loads(prior_path.read_text()) if prior_path.exists() else []
        all_centroids = build.merge_centroids(centroids, prior_index)
        storage.write_json({"generated_today": today,
                            "cities": sorted({r["city"] for r in all_daily})},
                           build.META / "city_list.json")
        storage.write_json(build.build_coverage(all_daily), build.META / "coverage.json")
        storage.write_json(build.build_cities_index(all_daily, all_centroids),
                           build.META / "cities.json")

    # Drip bookkeeping: mark this batch attempted (even cities that yielded no data) so the next
    # fire advances instead of re-selecting empties. Written after the run, so a crash mid-batch
    # leaves them un-attempted and they retry next time.
    if args.next_batch and args.cities:
        ap_path = build.META / "backfill_attempted.json"
        prev = json.loads(ap_path.read_text()).get("cities", []) if ap_path.exists() else []
        storage.write_json({"cities": plan.record_attempted(prev, args.cities)}, ap_path)

    n_cities = len({r["city"] for r in daily_rows})
    print(f"[run] done. daily_rows={len(daily_rows)} hourly_rows={len(hourly_rows)} "
          f"live_cities={live_count} daily_cities={n_cities}")


if __name__ == "__main__":
    main()
