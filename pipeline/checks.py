"""Pipeline health checks for CI alerting.

`newest_live_age_hours` returns how old the freshest live snapshot is, so a workflow can
fail (and open an issue) when today's data goes stale — e.g. CPCB is down and keep-last-good
left the snapshots untouched, so the run itself exits 0 but the data is old.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


def newest_live_age_hours(live_dir, now: dt.datetime | None = None) -> float | None:
    """Age (hours) of the newest data/live/*.json by its `updated_utc`. None if no usable file."""
    now = now or dt.datetime.now(dt.timezone.utc)
    newest: dt.datetime | None = None
    for f in Path(live_dir).glob("*.json"):
        try:
            ts = json.loads(f.read_text()).get("updated_utc")
            t = dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
        if newest is None or t > newest:
            newest = t
    if newest is None:
        return None
    return (now - newest).total_seconds() / 3600.0


def read_coverage(meta_dir) -> tuple[int | None, int | None]:
    """(city count, total station count) from a meta dir. Each is None if its file is missing."""
    meta = Path(meta_dir)
    try:
        cities = len(json.loads((meta / "city_list.json").read_text()).get("cities", []))
    except Exception:
        cities = None
    try:
        stations = sum(c.get("n_stations", 0)
                       for c in json.loads((meta / "cities.json").read_text()))
    except Exception:
        stations = None
    return cities, stations


def _drop(prior: int | None, current: int | None) -> float | None:
    """Relative drop (prior -> current); None when prior is missing or zero (metric skipped)."""
    if not prior or current is None:
        return None
    return (prior - current) / prior


def coverage_verdict(
    prior_cities, current_cities, prior_stations, current_stations,
    max_city_drop: float = 0.05, max_station_drop: float = 0.10,
) -> tuple[bool, str]:
    """Compare published coverage against the prior run. Alerts only on a DROP beyond threshold;
    growth never trips, and a missing/zero prior skips that metric."""
    problems = []
    cd = _drop(prior_cities, current_cities)
    if cd is not None and cd > max_city_drop:
        problems.append(
            f"cities {prior_cities} -> {current_cities} ({cd:.0%} > {max_city_drop:.0%})")
    sd = _drop(prior_stations, current_stations)
    if sd is not None and sd > max_station_drop:
        problems.append(
            f"stations {prior_stations} -> {current_stations} ({sd:.0%} > {max_station_drop:.0%})")
    if problems:
        return False, "COVERAGE DROP: " + "; ".join(problems)
    return (True,
            f"OK: coverage cities {current_cities} (prior {prior_cities}), "
            f"stations {current_stations} (prior {prior_stations})")


def _run_staleness(live_dir, max_hours) -> int:
    age = newest_live_age_hours(live_dir)
    if age is None:
        print(f"No live snapshot in {live_dir} yet - skipping staleness check.")
        return 0
    if age > max_hours:
        print(f"STALE: newest live snapshot is {age:.1f}h old (> {max_hours}h)")
        return 1
    print(f"OK: newest live snapshot is {age:.1f}h old")
    return 0


def _run_coverage(baseline, current, max_city_drop, max_station_drop) -> int:
    pc, ps = read_coverage(baseline)
    if pc is None and ps is None:
        print(f"No baseline coverage in {baseline} yet - skipping coverage check.")
        return 0
    cc, cs = read_coverage(current)
    ok, msg = coverage_verdict(pc, cc, ps, cs, max_city_drop, max_station_drop)
    print(msg)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("staleness")
    s.add_argument("--live-dir", required=True)
    s.add_argument("--max-hours", type=float, default=6.0)
    c = sub.add_parser("coverage")
    c.add_argument("--baseline", required=True)
    c.add_argument("--current", required=True)
    c.add_argument("--max-city-drop", type=float, default=0.05)
    c.add_argument("--max-station-drop", type=float, default=0.10)
    args = ap.parse_args()
    if args.cmd == "staleness":
        return _run_staleness(args.live_dir, args.max_hours)
    return _run_coverage(args.baseline, args.current, args.max_city_drop, args.max_station_drop)


if __name__ == "__main__":
    sys.exit(main())
