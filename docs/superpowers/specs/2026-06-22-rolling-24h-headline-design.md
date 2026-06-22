# Rolling-24h headline from OpenAQ hourly — design

Date: 2026-06-22
Status: approved (pending spec review)
Closes issue #5 (the remaining piece after the hourly-primary daily rollup).

## Problem

The headline reading is ~1-2 days old. The intended live source (CPCB) has been down the whole
project, so `data/live/*.json` (which the headline reads first) is never populated, and the
`run.py hourly` cron is effectively a no-op (it only tries CPCB). Meanwhile OpenAQ `/hours` is only
~3 hours behind real time and we already fetch and store it.

## Goal

Make the headline a **rolling 24-hour AQI computed from the latest OpenAQ hourly readings**, so the
hero number reads "a few hours ago" instead of "two days ago". Fall back to the latest daily row
where recent hourly is missing. This makes CPCB optional rather than load-bearing.

## Cadence decision (cost)

Each full-fleet hourly fetch is ~3263 OpenAQ calls (~1h at the 60/min pacing) — the same unit of
work regardless of frequency. A 24-hour rolling average barely moves hour-to-hour, and OpenAQ lags
~3h regardless, so fetching every hour buys imperceptible freshness for ~4x the API load and
saturates the serialized `data-refresh` lane. **Decision: refresh every ~4 hours** (`17 */4 * * *`)
— headline ~3-7h fresh, ~6 fetches/day, lane mostly free, gentle on OpenAQ.

## Pipeline — rework `run.py hourly` mode

Currently `hourly` mode does nothing useful (CPCB-only). Rework it to:

1. Fetch recent OpenAQ `/hours` for a short window (`--recent-days 2`, same shape as daily).
2. Assemble + upsert the recent hourly tier (`data/recent/`) from that fetch (keeps it warm; free).
3. **Compute a trailing-24h aggregate per city** (new `aggregate.rolling_24h`): for each city, find
   its most recent available hour, take the 24h window ending there, and compute the **arithmetic
   mean per pollutant** (same method as the daily rollup and OpenAQ's own `summary.avg`). Emit a
   per-city set of `CityPollutantRecord`s with `datetime_utc` = the most recent hour, `source =
   "openaq"`. A pollutant is included only if it has **≥12 of 24 hours** in the window; cities with
   no qualifying pollutant produce no live snapshot (they fall back to their daily row).
4. Write each city's snapshot via the existing `storage.live_snapshot(...)` →
   `storage.write_live_json(...)`, with `updated_utc` = the most recent hour's UTC timestamp.
5. **CPCB precedence preserved:** if a CPCB key is present and returns data, CPCB wins (it is the
   true real-time source). The rolling-24h path is the fallback when CPCB is absent.

`backfill` and `daily` modes are unchanged (daily still self-computes the calendar-day tier).

## Frontend

The headline already reads `live/*.json` first (flagging `>6h` as stale) and falls back to the
latest daily row, so the fallback ladder is mostly in place:

> CPCB live → OpenAQ rolling-24h (≥12h coverage) → latest daily row → >30-day stale-monitor notice.

Changes:

- **Subtitle (rolling case):** `<n> stations · OpenAQ · 24h average · as of <HH:MM> IST, <N>h ago`.
  The `as of` time is the most recent hour (time-only IST); the relative `<N>h ago` disambiguates.
  The daily-fallback case keeps the line shipped in #9 (`latest reading · <date>, <N> days ago`).
- **Notice:** when a rolling reading exists, the current "Live data (CPCB) is currently
  unavailable…" banner is **not shown** (it is no longer accurate). The daily-fallback and
  >30-day stale notices are unchanged.
- **"i" tooltip on the headline (transparency):** export the existing `InfoDot` helper from
  `SectionTitle.tsx` and add it to the headline. Copy: "A rolling average of the last 24 hours of
  hourly readings (OpenAQ), labelled with the most recent hour. Updated every few hours." Satisfies
  [[surface-methodology-on-site]].
- The `>6h` "stale" flag should no longer read as an error for a rolling reading — a few-hours-old
  rolling average is expected. The subtitle simply shows its age; the alarming "may be delayed"
  wording is dropped for the rolling case.

## Data contract

`data/live/<city>.json` keeps its existing `live_snapshot` shape (concentrations, per-pollutant
sub-indices, AQI for all three standards, `updated_utc`, `source`). The only change is that
`source` is now commonly `"openaq"` and `updated_utc` is the most recent hourly instant rather than
a CPCB timestamp. No frontend type change required (`LiveSnapshot` already covers it).

## Components touched

- `pipeline/transform/aggregate.py` — add `rolling_24h(hourly, *, min_hours=12, window_hours=24)`.
- `pipeline/run.py` — rework the `hourly` mode branch to fetch `/hours`, build the recent tier,
  compute the rolling-24h, and write live snapshots; keep CPCB precedence.
- `.github/workflows/refresh-hourly.yml` — cron `17 * * * *` → `17 */4 * * *`.
- `web/src/components/SectionTitle.tsx` — export `InfoDot`.
- `web/src/components/Headline.tsx` — rolling subtitle, notice handling, `InfoDot` tooltip.
- Tests in `pipeline/transform/test_aggregate.py`.

## Testing

TDD, unit-first:
- `rolling_24h`: full 24h → mean; partial ≥12h → included; <12h → excluded; per-pollutant
  coverage; window ends at the city's most recent hour (older rows outside the window ignored);
  `updated_utc` = most recent hour.
- Frontend: render check that the rolling subtitle shows "24h average · as of … IST, …h ago", the
  CPCB-unavailable banner is hidden when a rolling reading is present, and the InfoDot renders.
- Live verification: a scoped `run.py hourly --cities Delhi Mumbai` produces `data/live/*.json` with
  `source=openaq` and a recent `updated_utc`; preview shows the rolling headline.

## Out of scope / follow-ups

- Per-pollutant standards-correct windows (US O3 8h-max etc.) — issue #8.
- Backfilling historical rolling values — not needed; this is a live/current concern only.

## Risks

- **Coverage dips** (OpenAQ outage) → fewer cities get a rolling value that cycle; they fall back to
  the daily row honestly. Acceptable.
- **Fetch cost** — every-4h cadence keeps OpenAQ load and lane contention low; revisit only if we
  want fresher.
- **Method consistency** — rolling-24h uses the same mean as the daily rollup, so the headline and
  the daily tier are methodologically aligned (no jarring jump when a city flips between them).
