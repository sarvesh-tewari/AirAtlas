# AirAtlas — session handoff

Context-transfer doc so work can continue in a fresh Claude Code chat **without losing
anything**. Open Claude Code in this folder (`/Users/sarveshtewari/claude/AQI Dashboard`) and
the project memory auto-loads; then read this doc + `SOURCES.md` + `git log` for full context.

## What AirAtlas is
A free, open-source, public dashboard of India air quality (AQI) + weather for ~285 cities.
Default standard NAQI, toggle to US EPA AQI and EU EAQI — all computed from **raw pollutant
concentrations** (AQI is a *formula, not a measurement*). Static site + scheduled data pipeline.

## Status (as of this handoff — 2026-06-14)
- **Live:** https://sarvesh-tewari.github.io/AirAtlas/ — fully built + deployed (public repo).
- **Full backfill COMPLETE: 287 cities**, AQI 2016+ (where OpenAQ has it), all 3 standards. The
  self-chaining drip ran to completion overnight + self-disabled. Weather complete for all cities.
- **Brand redesign + logo shipped**: Inter, light/dark via `[data-theme]`, flat category-tint
  hero, eyebrow pills, section rhythm; theme-aware AirAtlas logo (topbar/favicon/About/splash).
- **84 backend tests green; web build clean; CI + deploy green** (actions bumped to Node24 majors).
- **Data is ~1 day stale BY NATURE:** CPCB live source is down, so site shows ~yesterday, not
  "today" — an honest banner explains it. Two HIGH-priority backlog items address this (see below).

## Architecture (1 paragraph)
`pipeline/` (Python): `aqi/` engine (NAQI/US/EU breakpoints + sub-index), `ingest/` (cpcb.py,
openaq.py, openmeteo.py, records.py, http.py), `transform/` (aggregate.py, reconcile.py,
citymap.py, storage.py), `build.py` + `run.py` orchestration, `checks.py`. Writes per-city
Parquet (`data/history` daily, `data/recent` hourly) + `data/live/*.json` + `data/meta/*.json`.
`web/` (React+Vite+TS+Tailwind v4 + DuckDB-WASM + ECharts + Leaflet) reads those files; AQI is
**precomputed in the pipeline** (single tested engine), frontend just renders. GitHub Actions:
`ci.yml` (lint+tests+web build), `refresh-hourly.yml`, `refresh-daily.yml` (hydrate data from
the `data` branch → run pipeline → publish back to the `data` branch), `deploy.yml` (fetch data
from the `data` branch + build+publish to Pages; triggered on push, dispatch, and workflow_run).

## Locked decisions (don't relitigate)
- Repo name **AirAtlas**; license **MIT** (code) + **CC BY 4.0** (data); host **GitHub Pages**.
- AQI **precomputed in pipeline**, not browser. City value = **mean concentration across
  stations**, computed identically for all 3 standards (plan §8.5; documented deviation from
  CPCB's sub-index-averaging city rule).
- **EU EAQI = current 2024 EEA bands** (user-approved); §7 EU expectation corrected to "Very Poor".
- **Theme = user's brand design system (2026-06-14, supersedes the old Manrope "Slate Modern")**:
  Inter font; tokens in `:root` + `[data-theme="dark"]` (web/src/index.css); flat category-tint
  hero (no gradient); eyebrow pills + section rhythm; AQI category palette kept as the data layer
  (exempt from the one-accent rule). Headline = gauge/dial; single scrolling page; About separate.
  **NO EM-DASHES** anywhere in copy (user pref — see [[no-em-dashes]] memory).
- Default city = **geolocate → nearest covered city, fallback Delhi**.
- Extra metrics added beyond the plan: **Monthly heatmap**, **Year-by-year** summary.

## Working agreements with the user (IMPORTANT — also in memory)
- Go **one phase/step at a time**; stop for review after each; don't rush.
- **Always confirm assumptions** for anything not explicitly stated.
- **UI decisions are checkpoints** — present options/mockups and get sign-off before building UI.
- Apply **user-centred design proactively** (hide irrelevant controls per view, empty/loading/
  error states, accessibility, responsiveness) — don't wait to be told.
- **Show screenshots as you go** to catch issues early and save tokens.

## Open / deferred items (prioritised)
1. ~~**Data out of git**~~ ✅ DONE (2026-06-13): data now lives on an orphan `data` branch as a
   single **parentless, force-pushed** commit (rolling snapshot — branch + main history both stay
   lean). `main` tracks only `.gitkeep` placeholders under `data/`. Refresh workflows hydrate from
   the branch (pipeline UPSERTS, so prior data must be present) → run → publish back; `deploy.yml`
   fetches the branch + stages into `web/public/data`. Mechanics: seed/publish via a throwaway
   `GIT_INDEX_FILE` (`git add -f data` → `write-tree` → parentless `commit-tree` → force-push);
   deploy/hydrate via `git archive origin/data data | tar -x`. Tree-equality check skips no-op
   redeploys. The two refresh crons are serialized by `concurrency: data-refresh`.
2. ~~**Full backfill**~~ ✅ DONE (2026-06-14): 287 cities via the self-chaining drip.
3. **[BACKLOG · HIGH] Fill the 2023–2024 gap.** EVERY city is missing ~Nov 2022 → Jan 2025 (~27mo)
   — an OpenAQ ingestion lapse (data genuinely absent from OpenAQ, not our bug; confirmed across
   all 286 cities). User wants it filled FROM CPCB (provenance match). Plan: one-time scrape of CCR
   `POST app.cpcbccr.com/caaqms/fetch_table_data` (base64-JSON body via `data=`, no captcha/auth —
   open API; payload shape from gsidhu/cpcbccr-data-scraper setup_pull.py), aggregate via our
   pipeline, upsert into parquet by date (like the weather-fill), keep raw archive. Since it's a
   finite historical window, scrape ONCE → store → done (portal fragility irrelevant).
   **BLOCKED right now:** CPCB infra is down — CCR = Cloudflare 526 (origin SSL), airquality.cpcb
   .gov.in self-signed, data.gov.in times out. Step when unblocked: confirm 1 station/2023 → run
   once. Fallback: vet archival/Kaggle datasets (MUST have RAW concentrations + city coverage).
4. **[BACKLOG · HIGH] Re-architect freshness to OpenAQ-hourly-primary** (user to approve; NOT
   started). CPCB "today" source is down + load-bearing; OpenAQ HOURLY is only ~3h behind (checked
   40/287: median 3.3h, ~12% no recent hourly). Plan: live headline = rolling-24h AQI from latest
   OpenAQ hourly (we already fetch 90d hourly), fall back to latest daily; makes CPCB optional.
5. **[BACKLOG · low] citymap mis-parse cleanup**: "DN Park" (+ earlier Noida, now fixed) are bad
   city names from `city_from_station_name`; add aliases in `pipeline/config/city_aliases.json`.
6. Full US **O3 1h / SO2 24h** hybrid curves (capped at tabulated max); failure-issue dedup/spam;
   daily coverage-floor health check; recent-tier hourly weather join; Year-by-year as a chart.

## Backlog from user feedback (2026-06-14) — NOT yet done
A. **Smoke + regression tests.** SMOKE = a NEW lightweight post-deploy live check (in `deploy.yml`
   after publish; runs on every change/deploy): assert live URL 200, `city_list.json` non-empty,
   data files load, no console errors. REGRESSION = the existing 84-test pytest + web build; run
   AUTOMATICALLY on all major changes, NO approval gate (user revised from "confirm first"). CI
   already runs the suite on push — formalize/name it as the regression gate.
B. **Proactive alerting + uptime.** Channel = GitHub issues (user Watches repo → email); already
   auto-opens on pipeline failure. KEEP that for pipeline-fail + data-stale. ADD an external
   UPTIME/synthetic check (Actions can't see live-site health): scheduled load of the live URL,
   assert it renders + has data, open an issue (→email) on failure. Goal: user is alerted to
   pipeline-fail / data-stale / site-down WITHOUT checking the site.
C. **De-phase + clean the PUBLIC repo (think senior-dev).** REMOVE internal docs from the repo —
   THIS `HANDOFF.md`, the build-plan doc, `docs/SETUP.md` — via `git rm --cached` + gitignore (keep
   them locally for continuity). Scrub "Phase N" language from README/SOURCES/code comments. Write a
   proper public README (what it is, live URL, how-to-use, data sources + attribution "CPCB via
   OpenAQ", license). LEAVE git history as-is (no rewrite — user agreed).
D. **Add live URL to GitHub** — repo About→Website field (`gh api`) + a README link/badge.
E. **Info "i" buttons per dashboard box/chart** — reuse the existing info-tooltip pattern; concise
   per-box copy (gauge/map/pollutants/trend/heatmap/year-by-year/pollutant-trends/exceedance/weather/
   compare). UI checkpoint → draft copy, show user.
F. **Data-quality audit.** Investigate Ariyalur AQI=500 (and WHY it's dated Jun-14 when the latest
   should be ~the 13th); project-wide sweep for off-scale/implausible values that slipped past
   `drop_implausible`; decide spike-vs-legit per case (500 is legit in a Delhi winter but suspect for
   a small Tamil Nadu city in summer); tighten filtering only where it's a clear sensor artifact.

## Known gotchas / lessons (so they aren't re-hit)
- **CPCB infra is fully DOWN (2026-06-14)**: data.gov.in times out; CCR (app.cpcbccr.com) = Cloudflare
  526 (origin SSL invalid); airquality.cpcb.gov.in is self-signed; only static cpcb.nic.in works.
  So there's NO live "today" source; pipeline keeps last-good + the headline shows a ~1-day lag.
- **OpenAQ HOURLY is near-real-time (~3h lag)** but we only use OpenAQ `/days` (~1-day lag) for the
  headline (backlog #4 fixes this). OpenAQ has NO India data Nov2022–Jan2025 (backlog #3).
- **Weather (Open-Meteo archive): `end_date` must be YESTERDAY** (today → HTTP 400 "out of range");
  it also has a WEIGHTED minute rate-limit (~5 heavy full-history calls/min → 429). Paced via
  `AIRATLAS_WEATHER_REQUEST_INTERVAL` (15s backfill / 3s daily) + a 60s 429-retry floor (`http._retry_wait`).
- **Drip self-chains via the `DRIP_PAT` repo secret** (GITHUB_TOKEN can't trigger workflow_dispatch).
  GitHub's *cron* scheduler is unreliable (stalled 12h once) → refresh-daily has 2 fires/day and is
  scoped to published cities (`plan.daily_cities`) so it never publishes thin 1-day cities.
- **OpenAQ quirks**: provider id 168 = CPCB; `/days` uses `date_from/date_to`, `/hours` uses
  `datetime_from/datetime_to`; multi-year series split across sensor ids; **CO is mislabeled
  "ppb" but is really mg/m³** (handled by magnitude); gases often ppb → normalized to µg/m³.
- **Dirty data**: sensor errors (PM2.5 > PM10, SO2 spikes) filtered by `drop_implausible`.
- **DuckDB-WASM** returns int64 as **BigInt** — coerce to Number (done in `lib/duckdb.ts`).
- **GitHub Actions**: a push made by a workflow token does NOT re-trigger `push` workflows →
  `deploy.yml` uses a `workflow_run` trigger. Refreshes now **force-push a self-contained
  parentless tree to the `data` branch** (not main), so the old `git pull --rebase before push`
  dance is gone; the `concurrency: data-refresh` group serializes the two crons so they never
  race the force-push. (Human pushes to `main` are unaffected — refreshes never touch main.)
- **Orphan `data` branch publish**: build the commit in a **throwaway `GIT_INDEX_FILE`** (subshell-
  scoped — if it leaks into a later `git status`, that shell sees an empty index and reports every
  file "deleted"; the real index is fine). Refspecs use **`${VAR}:refs/...` braces** — bare
  `$VAR:refs` triggers zsh's `:r` modifier locally (mangled the first push). On Actions (bash) it's
  moot, but brace anyway.
- **Pages base path** is hardcoded `/AirAtlas/` (VITE_BASE in deploy.yml) — matches repo name.
- **Preview screenshots** capture only the top viewport and fire before DuckDB finishes (~2-3s)
  — verify below-fold/loaded content via `preview_eval` DOM checks, not just screenshots.
- Secrets/keys are whitespace-stripped in code (a leading space once broke the X-API-Key header).

## How to run things
```bash
# Pipeline (Python)
cd pipeline && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
python -m pytest -q            # 84 tests
python -m ruff check .
# Local one-off (needs ../.env with OPENAQ_API_KEY; DATA_GOV_IN_KEY optional + currently down):
python run.py backfill --cities Delhi --sensors all   # or --next-batch N for drip self-select

# Frontend (Node)
cd web && npm install
npm run dev          # dev server (launch.json name "web", port 5173)
npm run build        # tsc --noEmit + vite build

# Deploy / data (GitHub)
gh workflow run refresh-daily.yml -f mode=backfill    # full/curated backfill
gh run watch <id>                                     # watch a run
```
Local dev data: `web/public/data` is a symlink to `../../data` (gitignored). `.env` is gitignored.
Generated `data/` is dev-gitignored and **not on `main`** — it lives on the orphan `data` branch
(see deferred item 1). `main` keeps only `.gitkeep` placeholders so the dir structure survives a
fresh clone. To inspect the live dataset: `git fetch origin data && git archive origin/data data | tar -t`.
