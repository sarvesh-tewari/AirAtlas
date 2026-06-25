# Daily coverage-floor health check — design

Date: 2026-06-25
Status: approved (pending spec review)
Implements issue #11.

## Problem

We alert on pipeline failures (a run that errors) and on stale data (the smoke check on
`generated_today`), but not on a quiet **coverage drop**: a `refresh-daily` that *succeeds*
(exits 0) yet publishes far fewer cities or stations than usual. A partial upstream outage that
still returns *some* data slips through silently.

## Goal

After a daily refresh, before publishing, compare the new published coverage against the previous
run's and fail (with an informative alert) if it dropped sharply. Failing before publish keeps the
prior good data on the `data` branch rather than overwriting it with a thin set.

## Metric

Check two counts, derived from the meta the pipeline already writes:
- **City count** = length of `city_list.json` `cities`.
- **Total station count** = sum of `n_stations` across `cities.json`.

Alert if **either** drops more than its threshold. The station count catches a partial outage where
the city list is unchanged but sensors per city vanish.

## Baseline (option A: previous published counts)

No new persistent state. The daily run already hydrates the prior `data` branch into `data/` at the
start, so the previously-published meta is on disk *before* the pipeline overwrites it. The workflow
captures it: immediately after the Hydrate step (and before the Refresh step that overwrites it),
copy `data/meta/city_list.json` and `data/meta/cities.json` into a baseline dir
(`/tmp/coverage-baseline/`). The check then compares the new `data/meta` against that snapshot.

Because the check runs before publish and fails on a sharp drop, a thin set never gets published,
so the baseline is always "the last *good* published coverage" (it cannot self-poison downward).

## Thresholds

Per-metric relative drop, configurable:
- **City count: 5%** (`--max-city-drop 0.05`). The published city set is derived from
  `read_all_daily` (every history parquet on disk), so it is stable or growing by construction; a
  5% drop is genuinely anomalous.
- **Station count: 10%** (`--max-station-drop 0.10`). Per-city sensor counts naturally wobble more,
  so a wider band avoids false alarms.

## Placement

In `.github/workflows/refresh-daily.yml`, a new step **after** "Refresh history + recent" and
**before** "Publish data to data branch":
1. (after Hydrate) capture the baseline meta to `/tmp/coverage-baseline/`.
2. (after Refresh) run the coverage check; on a sharp drop it exits non-zero, the run fails, the
   "Publish" step is skipped (prior good data retained), and the existing "Open/append failure
   issue" step fires with the check's `COVERAGE DROP: …` output.

## Code shape

Extend `pipeline/checks.py` into a small multi-check CLI using argparse **subcommands**:
- `checks.py staleness --live-dir <dir> --max-hours <n>` — the existing live-snapshot check (its
  logic and behavior are unchanged; only the invocation gains the `staleness` subcommand).
- `checks.py coverage --baseline <dir> --current <dir> --max-city-drop 0.05 --max-station-drop 0.10`
  — the new check.

The one existing caller, `refresh-hourly.yml`, is updated from `checks.py --live-dir … --max-hours …`
to `checks.py staleness --live-dir … --max-hours …`.

The coverage logic is a **pure comparator** so it is unit-testable without files:

```
coverage_verdict(prior_cities, current_cities, prior_stations, current_stations,
                 max_city_drop, max_station_drop) -> (ok: bool, message: str)
```

A thin file-reading wrapper loads the counts from the two dirs and calls it. Drop is computed as
`(prior - current) / prior` per metric; a value above the metric's threshold trips. Growth (current
>= prior) never trips.

## Edge cases

- **No baseline** (first run, or baseline files missing/empty): skip with a message
  (`No baseline coverage yet - skipping coverage check.`) and exit 0, mirroring how the staleness
  check skips when there is no live data.
- **Baseline count 0** for a metric: skip that metric (avoid divide-by-zero).
- **Growth:** never alerts; only a drop beyond threshold does.
- Both metrics are independent; a trip on either fails the run, and the message names which dropped.

## Testing

TDD on the pure comparator (`pipeline/test_checks.py`, which exists):
- city drop > 5% trips; city drop < 5% ok.
- station drop > 10% trips; station drop < 10% ok.
- a 6% drop trips on city but a 6% station drop does not (per-metric thresholds honored).
- growth on both -> ok.
- zero prior count -> that metric skipped, no divide-by-zero.
- the message names the offending metric with the percentages.

Then a manual run of `checks.py coverage` against a real baseline + current meta to confirm the
file wrapper and the exit codes.

## Out of scope / follow-ups

- **#12 (alert throttling + auto-resolve):** until that lands, a *sustained* coverage drop re-alerts
  on each daily run (appending to the one failure issue). Acceptable; #12 will throttle it.
- No rolling-history baseline (option C). The published city count is stable by construction, so the
  noise-smoothing C would add is unnecessary, and it would introduce new persistent state with
  self-poisoning failure modes.

## Risks

- **Legitimate large drops** (e.g. a deliberate dataset change) would trip the check and require a
  manual run/close. Rare; acceptable, and better than silent under-coverage.
- Threshold tuning: 5% / 10% are starting points; if false alarms appear they are one-line config
  changes in the workflow.
