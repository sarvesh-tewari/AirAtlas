# AirAtlas — session handoff

Context-transfer doc so work can continue in a fresh Claude Code chat **without losing
anything**. Open Claude Code in this folder (`/Users/sarveshtewari/claude/AQI Dashboard`) and
the project memory auto-loads; then read this doc + `SOURCES.md` + `git log` for full context.

## What AirAtlas is
A free, open-source, public dashboard of India air quality (AQI) + weather for ~285 cities.
Default standard NAQI, toggle to US EPA AQI and EU EAQI — all computed from **raw pollutant
concentrations** (AQI is a *formula, not a measurement*). Static site + scheduled data pipeline.

## Status (as of this handoff)
- **Live:** https://sarvesh-tewari.github.io/AirAtlas/ (GitHub Pages, public repo
  `sarvesh-tewari/AirAtlas`). Currently populated with a **14-city demo subset** (2024+).
- **Phases 1–9 complete; Phase 10 (deploy) live.** Repo pushed, Actions secrets set, Pages on,
  hourly/daily refresh crons running, auto-deploy wired.
- **70 backend tests green; web typecheck + build clean; CI green.**
- A full **senior code-review hardening pass** was completed (commit `93f6186`).

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
- **Theme = "Slate Modern" + warm/slate option C**: Manrope font, warm-paper light surfaces,
  slate-blue dark mode, ink-blue accent. AQI headline = **gauge/dial**. Single scrolling page;
  Methodology/About separate. Colourful per-section icon chips. Colour always paired with label.
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
2. **Full backfill**: currently 14 demo cities. Run all ~285 via
   `gh workflow run refresh-daily.yml -f mode=backfill` (long; resumable; auto-deploys).
3. **CPCB live verification**: data.gov.in was DOWN the entire project — the `cpcb.py` path is
   tested vs a fixture only. Verify with `python pipeline/run.py hourly` once it recovers.
4. Full US **O3 1h / SO2 24h** hybrid curves (currently capped at the pollutant's tabulated max).
5. Failure-issue **dedup race / comment spam** on long outages; **daily coverage-floor** health check.
6. Recent-tier **hourly weather join** (daily weather works; hourly overlay not yet joined).
7. Optional: **Year-by-year as a chart** (offered, not built).

## Known gotchas / lessons (so they aren't re-hit)
- **data.gov.in (CPCB)** is flaky/down — code retries + keeps last-good; live path unverified live.
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
python -m pytest -q            # 70 tests
python -m ruff check .
# A local build (needs ../.env with DATA_GOV_IN_KEY + OPENAQ_API_KEY):
python run.py daily --cities Delhi Mumbai --max-per-city 4 --from 2024-01-01 --sensors first

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
