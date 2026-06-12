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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-dir", required=True)
    ap.add_argument("--max-hours", type=float, default=6.0)
    args = ap.parse_args()

    age = newest_live_age_hours(args.live_dir)
    if age is None:
        print(f"STALE: no usable live snapshot in {args.live_dir}")
        return 1
    if age > args.max_hours:
        print(f"STALE: newest live snapshot is {age:.1f}h old (> {args.max_hours}h)")
        return 1
    print(f"OK: newest live snapshot is {age:.1f}h old")
    return 0


if __name__ == "__main__":
    sys.exit(main())
