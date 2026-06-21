# Hourly-primary pipeline + self-computed daily rollup — design

Date: 2026-06-21
Status: approved (pending spec review)
Supersedes the "bump generated_today" idea; closes the bulk of issue #5.

## Problem

The scheduled daily refresh reports `success` but the dashboard's freshness never advances,
so deploy + uptime smoke checks go red. Root-caused on 2026-06-21:

1. **Malformed daily request.** The daily window is `yesterday..yesterday`, i.e.
   `date_from == date_to`. OpenAQ `/days` rejects equal dates with **HTTP 422**
   ("Date from must be older than the date to"). All 3263 daily sensor calls 422'd →
   `daily_rows = 0`. (~1 hour wasted.)
2. **`generated_today` only advances when daily rows land.** It is written inside
   `if daily_rows:` ([run.py:240](../../../pipeline/run.py)), so with `daily_rows = 0` it stays
   frozen (06-16) even though the run published (the hourly tier changed).
3. **The `/days` aggregate lags badly.** Even with a valid window, `/days` returns 0 results for
   recent India days across all sampled sensors. The daily tier is effectively dead at ~06-15.
4. **The fresh data is in `/hours`, unused.** The run pulled the recent (hourly) tier current to
   **2026-06-20T22:30Z for 249 cities** — but nothing reads it for the headline/freshness.
5. **The run takes ~4h38m** (under the 330-min cap, not comfortably): ~1h on the 422 daily loop +
   ~3h38m on the hourly fetch. At OpenAQ's 60 req/min cap, fetching every sensor twice (once
   `/days`, once `/hours`) is a ~108-min pacing floor before any retries.
6. **Logs are undebuggable.** Failures log only `type(e).__name__` ("HTTPStatusError"), discarding
   the status code, window, and URL.

## Goal

Make the dashboard's daily numbers and freshness reflect the freshest data we actually hold,
using a single upstream endpoint, fast enough to run comfortably under the cap, with logs that
explain failures.

## Core design: hourly-primary, we own the daily rollup

- **OpenAQ API: only `/hours`** going forward (plus the cheap `/locations` discovery, live CPCB
  when available, and weather). We never call `/days` again in the routine pipeline.
- **We compute the daily value ourselves** by rolling each day's hourly readings up into a per-city
  daily concentration, then computing AQI from it — identical to how the dashboard consumes the
  daily tier today.
- **We store the computed daily value** in the existing daily/history tier (`data/history`).
- **The dashboard is unchanged** — it still reads daily numbers from our stored files. It does not
  know the number now comes from our hourly rollup instead of OpenAQ `/days`.

Net effect: one endpoint, each sensor fetched once (~halves the run), the daily tier advances on
its own (no headline/freshness mismatch), and most of issue #5 is closed.

### Historical data

The existing `data/history` tier (2016+, built from `/days` backfill) is kept as-is. Only *new*
days are computed from hourly going forward. We do not re-fetch `/days` history. The blocked
2023–24 gap (#4) is unaffected by this change.

## Aggregation method (proposed values — validated before cutover)

Operate on the **city-hour recent tier** we already build (`aggregate_to_city` already takes the
**median concentration across stations** per hour — the locked data-quality rule):

- **hour → city-day:** arithmetic **mean** of the day's available city-hour concentrations, per
  pollutant (the conventional 24-hour average). This **matches OpenAQ exactly**: the `/days`
  record's canonical value is `summary.avg` (the arithmetic mean of the day's hours — verified
  against the live API), and our parser already ingests `summary.avg`
  ([openaq.py:67](../../../pipeline/ingest/openaq.py)). So the historical `/days` tier and our new
  hourly-rollup days are computed identically — no methodology discontinuity. (OpenAQ also exposes
  `max`/`median`/quantiles, but neither OpenAQ's daily value nor our current pipeline uses them.)
- **per-pollutant averaging windows:** all pollutants use the 24h mean today, matching current
  behavior. The standards-specified **max 8-hour** windows for O3/CO (and 1h max for SO2/NO2) are
  **not** applied here — that is issue #8, deferred. Owning the hourly rollup makes #8 easier later.
- **coverage threshold:** a city-day pollutant value is computed only if **≥ 18 of 24 hours** are
  present for that pollutant (configurable via `AIRATLAS_MIN_DAILY_HOURS`, default 18). Rationale:
  CPCB NAQI requires a 16-hour minimum; 18 is a conservative default. Pollutants/days below the
  threshold are **omitted, never fabricated**. AQI is computed from whatever pollutants clear the
  bar (exactly how missing pollutants are already handled).
- **across stations:** unchanged — median across stations, already applied at the city-hour step.

Measured feasibility (2026-06-20): 249 cities present, median 23 hours, **232 cities ≥ 18 hours**.
Coverage is per-pollutant (e.g. Vijayapura: pm10/so2/o3 at 23h, pm25/no2/co at 0h → daily value
from pm10/so2/o3).

### Validation gate (before trusting the rollup)

The recent (hourly) tier and the `/days`-derived history tier **overlap** (~March → 06-15). For
those overlapping days, compute the hourly-rollup daily value and compare against the stored
`/days` value per city/pollutant. Require a close match (concentration within a small tolerance and
no AQI-category shifts on a representative sample) before cutting the dashboard over. If they
diverge materially, revisit the aggregation order (per-station-day mean → median across stations)
before shipping.

## Freshness signal

- `city_list.json` `generated_today` becomes **"data through" = max date present across the daily +
  recent tiers** (→ 06-20 today). Written on **every** successful run (remove the `if daily_rows:`
  gate), with the `cities` list read from the on-disk daily tier so it is **preserved even when no
  new rows landed** (never clobbered to empty).
- Field name kept as `generated_today` to avoid touching the frontend type + smoke check; a code
  comment documents the new meaning. (Rename deferred — only the smoke check reads it; the frontend
  loads but does not display it.)
- `scripts/smoke.mjs`: no logic change (its 4-day threshold now passes); comment refreshed.

## Logging

- Per-sensor skip lines include **status code, sensor id, city, period, and window**, e.g.
  `[build] skip sensor 13866 hours Delhi 2026-06-20..2026-06-21: HTTP 403`. Status extracted from
  `HTTPStatusError.response.status_code` (and surfaced through the wrapping `RuntimeError`).
- `http.get_json`'s `RuntimeError` includes the **final status code + URL**, not just the URL.
- A **per-tier summary line**: `[build] hours: 3263 sensors -> 2980 ok, 283 empty, 0 failed`, with
  failures broken down by status code. One glance explains the next incident.

## Components touched

- `pipeline/run.py` — drop the `/days` fetch from `daily` mode; fetch `/hours` only; compute the
  daily rollup from the recent tier; always-write freshness + preserved cities.
- `pipeline/transform/aggregate.py` (or a new `transform/rollup.py`) — hour → city-day rollup with
  per-pollutant coverage threshold. Keep the unit small and independently testable.
- `pipeline/build.py` — fetch summary counters; status-aware skip logging.
- `pipeline/ingest/http.py` — `RuntimeError` carries final status + URL.
- `scripts/smoke.mjs` — comment only.
- Tests under `pipeline/tests/`.

## Testing

TDD, unit-first:
- Rollup: ≥18h pollutant → daily mean; <18h pollutant → omitted; mixed-pollutant city; empty day.
- Freshness: `generated_today` = max across tiers; written when `daily_rows == 0`; `cities`
  preserved (not clobbered).
- Logging: summary counts ok/empty/failed; skip line carries status + window.
- Validation gate: rollup-vs-`/days` comparison on overlapping historical days (script + assertion
  on tolerance / category stability).

Then a scoped live daily run to confirm: `generated_today` → 06-20, daily tier advances, runtime
well down (~halved), deploy + uptime green.

## Out of scope (follow-ups)

- **#5 remainder:** a live rolling-24h headline (distinct from the self-computed *calendar*-day
  number this design adds).
- **#8:** US O3 (8h max) / SO2 hybrid curves — pollutant-specific averaging windows beyond the
  24h mean.
- **Map markers / `cities.json` `last_date`** already advance for free once the daily tier advances
  (helps #6), but the fade-stale-markers UI is its own issue.
- A separate infrequent `/days` catch-up job is **not** added; if `/days` ever recovers it can be a
  manual/backfill concern using a valid `from < to` window.

## Risks

- **Rollup fidelity.** Mitigated by the validation gate vs `/days` before cutover.
- **Per-day hourly coverage dips** (e.g. an OpenAQ outage) → fewer cities get a daily number that
  day; freshness reflects it honestly rather than fabricating. Acceptable.
- **Methodology discontinuity** between `/days`-derived history and hourly-rollup-derived new days.
  Mitigated by the validation gate; documented on the site per [[surface-methodology-on-site]].
