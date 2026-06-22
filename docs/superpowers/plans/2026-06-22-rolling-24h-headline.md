# Rolling-24h headline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the headline a rolling 24-hour AQI from the latest OpenAQ hourly readings (refreshed every ~4h), falling back to the latest daily row where recent hourly is missing.

**Architecture:** Rework `run.py hourly` mode to fetch recent `/hours`, compute a trailing-24h mean per city (`aggregate.rolling_24h`), and write it to `data/live/*.json` via the existing `live_snapshot` writer. The frontend already reads `live/*.json` first and falls back to the daily row, so the frontend change is just the subtitle copy, a notice tweak, and an "i" tooltip. CPCB still wins when present.

**Tech Stack:** Python 3.13 (polars, pytest, ruff) for the pipeline; React + Vite + TS for the web. Pipeline tests run from `pipeline/` via `.venv/bin/python -m pytest`. The web has no unit-test runner, so frontend tasks verify with `tsc --noEmit` + the browser preview.

**Spec:** `docs/superpowers/specs/2026-06-22-rolling-24h-headline-design.md`
**Branch:** `feat/rolling-24h-headline` (already created)

---

## File structure

- `pipeline/transform/aggregate.py` — **add** `rolling_24h()`. Pure, unit-tested.
- `pipeline/transform/test_aggregate.py` — **add** rolling tests.
- `pipeline/run.py` — **modify** the `hourly` mode branch (currently a CPCB-only no-op) to fetch `/hours`, compute the rolling-24h, and write live snapshots; extend the published-city scoping to hourly.
- `.github/workflows/refresh-hourly.yml` — **modify** cron to every 4h.
- `web/src/lib/format.ts` — **add** `formatTimeIST()`.
- `web/src/components/SectionTitle.tsx` — **export** the existing `InfoDot`.
- `web/src/components/Headline.tsx` — **modify** subtitle, notice, add `InfoDot` tooltip.

---

## Task 1: `rolling_24h` in aggregate.py

**Files:**
- Modify: `pipeline/transform/aggregate.py`
- Test: `pipeline/transform/test_aggregate.py`

- [ ] **Step 1: Write the failing tests** — append to `pipeline/transform/test_aggregate.py`:

```python
def test_rolling_24h_means_window_ending_at_latest_hour():
    # 24 hours of pm25 ending at 2026-06-20T12:00Z -> one record, mean, latest hour as the key.
    recs = [_hourly("Pune", "pm25", f"2026-06-19T{h:02d}:00:00Z", 40.0 + h) for h in range(13, 24)]
    recs += [_hourly("Pune", "pm25", f"2026-06-20T{h:02d}:00:00Z", 40.0 + h) for h in range(0, 13)]
    out = agg.rolling_24h(recs, min_hours=12)
    assert len(out) == 1
    r = out[0]
    assert r.city == "Pune" and r.parameter == "pm25"
    assert r.datetime_utc == "2026-06-20T12:00:00Z"  # most recent hour
    assert r.averaging == "24h"
    assert abs(r.value - (sum(40.0 + h for h in range(13, 24)) + sum(40.0 + h for h in range(0, 13))) / 24) < 1e-9


def test_rolling_24h_excludes_pollutant_below_min_hours():
    recs = [_hourly("Pune", "no2", f"2026-06-20T{h:02d}:00:00Z", 20.0) for h in range(0, 6)]  # 6 < 12
    assert agg.rolling_24h(recs, min_hours=12) == []


def test_rolling_24h_ignores_rows_older_than_window():
    # 12 fresh hours + an old reading 3 days earlier; the old one must not enter the window.
    recs = [_hourly("Pune", "pm25", f"2026-06-20T{h:02d}:00:00Z", 50.0) for h in range(0, 12)]
    recs.append(_hourly("Pune", "pm25", "2026-06-17T05:00:00Z", 999.0))
    out = agg.rolling_24h(recs, min_hours=12)
    assert len(out) == 1
    assert out[0].value == 50.0  # the 999 outlier is outside the 24h window, excluded


def test_rolling_24h_per_city_latest_hour():
    # Two cities with different latest hours; each window ends at its own latest.
    a = [_hourly("A", "pm25", f"2026-06-20T{h:02d}:00:00Z", 30.0) for h in range(0, 12)]
    b = [_hourly("B", "pm25", f"2026-06-19T{h:02d}:00:00Z", 60.0) for h in range(0, 12)]
    out = {r.city: r for r in agg.rolling_24h(a + b, min_hours=12)}
    assert out["A"].datetime_utc == "2026-06-20T11:00:00Z"
    assert out["B"].datetime_utc == "2026-06-19T11:00:00Z"
```

(The `_hourly` helper was added in the daily-rollup work — it builds a `CityPollutantRecord` with `averaging="1h"`. If it is absent, add it: see `test_rollup_*` tests at the top of the file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline && .venv/bin/python -m pytest transform/test_aggregate.py -k rolling_24h -v`
Expected: FAIL — `module 'transform.aggregate' has no attribute 'rolling_24h'`

- [ ] **Step 3: Implement `rolling_24h`** — add to `pipeline/transform/aggregate.py` (after `rollup_hourly_to_daily`):

```python
def rolling_24h(
    hourly: list[CityPollutantRecord], *, min_hours: int = 12, window_hours: int = 24,
) -> list[CityPollutantRecord]:
    """Per-city trailing-window mean from hourly city records, for the live headline.

    For each city, find its most recent available hour, take the `window_hours` window ending
    there, and compute the arithmetic MEAN per pollutant (same method as the daily rollup and
    OpenAQ's summary.avg). A pollutant is emitted only if it has >= `min_hours` readings in the
    window. The emitted record's datetime_utc is the city's most recent hour, so the live snapshot
    is stamped with the freshest reading time. Median-across-stations is already applied per hour.
    """
    def _ts(r: CityPollutantRecord) -> dt.datetime:
        return dt.datetime.fromisoformat(r.datetime_utc.replace("Z", "+00:00"))

    by_city: dict[str, list[CityPollutantRecord]] = defaultdict(list)
    for r in hourly:
        if r.value is not None:
            by_city[r.city].append(r)

    out: list[CityPollutantRecord] = []
    for city, rows in by_city.items():
        latest_row = max(rows, key=_ts)
        cutoff = _ts(latest_row) - dt.timedelta(hours=window_hours)
        window = [r for r in rows if _ts(r) > cutoff]
        by_param: dict[str, list[CityPollutantRecord]] = defaultdict(list)
        for r in window:
            by_param[r.parameter].append(r)
        for param, rs in by_param.items():
            if len(rs) < min_hours:
                continue
            values = [r.value for r in rs]
            covs = [r.coverage_pct for r in rs if r.coverage_pct is not None]
            out.append(CityPollutantRecord(
                city=city, parameter=param, datetime_utc=latest_row.datetime_utc,
                averaging="24h", value=sum(values) / len(values), unit=rs[0].unit,
                n_stations=max(r.n_stations for r in rs),
                coverage_pct=(sum(covs) / len(covs)) if covs else None, source="openaq",
            ))
    return out
```

This module imports `datetime as dt` at the top (added in the rollup work) and `defaultdict`. If `import datetime as dt` is not present at module scope, add it with the other imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && .venv/bin/python -m pytest transform/test_aggregate.py -k rolling_24h -v` → PASS (4).
Then the whole file: `cd pipeline && .venv/bin/python -m pytest transform/test_aggregate.py -q` and `cd pipeline && .venv/bin/python -m ruff check transform/aggregate.py transform/test_aggregate.py`.

- [ ] **Step 5: Commit**

```bash
git add pipeline/transform/aggregate.py pipeline/transform/test_aggregate.py
git commit -m "feat(pipeline): rolling_24h trailing-window mean for the live headline

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Wire `hourly` mode to compute + write the rolling-24h live snapshot

**Files:**
- Modify: `pipeline/run.py` (the published-city scoping condition; add a `hourly` block)

- [ ] **Step 1: Extend published-city scoping to hourly mode**

In `pipeline/run.py`, change the daily-scoping guard so it also scopes `hourly` runs to published cities:

```python
    if args.mode == "daily" and not args.next_batch:
```
to:
```python
    if args.mode in ("daily", "hourly") and not args.next_batch:
```
and update the two messages in that block from `"[run] daily: ..."` / `"daily scoped to"` to be mode-aware, e.g.:
```python
        if not args.cities:
            print(f"[run] {args.mode}: no published cities yet - nothing to refresh.")
            return
        print(f"[run] {args.mode} scoped to {len(args.cities)} published cities")
```

- [ ] **Step 2: Add the hourly block**

In `pipeline/run.py`, immediately AFTER the daily block (the `if args.mode in ("backfill", "daily"):` block that ends with `daily_rows = storage.assemble_daily_rows(...)`) and BEFORE the `# ---- Live snapshot (today) ----` comment, insert:

```python
    # ---- Rolling-24h live headline (hourly mode) ----
    # OpenAQ /hours is ~3h behind real time; CPCB (the true live source) is down. Compute a
    # trailing-24h mean per city and write it as the live snapshot. CPCB, if present, overrides
    # below. See docs/superpowers/specs/2026-06-22-rolling-24h-headline-design.md
    if args.mode == "hourly":
        recent_from = (dt.date.fromisoformat(today) - dt.timedelta(days=args.recent_days)).isoformat()
        print(f"[run] hourly: fetching recent hourly (last {args.recent_days}d)…")
        city_hourly = build.fetch_city_aq(oa_key, sel, mapping, date_from=recent_from,
                                          date_to=today, period="hours", sensors=args.sensors)
        hourly_rows = storage.assemble_hourly_rows(city_hourly)
        min_hours = int(os.environ.get("AIRATLAS_MIN_ROLLING_HOURS", "12"))
        rolling = aggregate.rolling_24h(city_hourly, min_hours=min_hours)
        print(f"[run] hourly: rolling-24h for {len({r.city for r in rolling})} cities "
              f"(min_hours={min_hours})")
        wx_now = build.fetch_weather_current(centroids)
        rolling_by_city: dict[str, list] = {}
        for r in rolling:
            rolling_by_city.setdefault(r.city, []).append(r)
        for rcity, recs in rolling_by_city.items():
            try:
                snap = storage.live_snapshot(rcity, recs, updated_utc=recs[0].datetime_utc,
                                             weather=wx_now.get(rcity))
                storage.write_live_json(snap, build.DATA / "live")
            except Exception as e:
                print(f"[run] rolling live snapshot skipped for {rcity}: {type(e).__name__}: {e}")
        print(f"[run] hourly: wrote {len(rolling_by_city)} rolling live snapshots")
```

Notes:
- `daily_rows` stays `[]` in hourly mode, so the daily-tier parquet write is skipped. `hourly_rows` is now set, so the recent-tier parquet write persists it.
- The existing CPCB live block (`if dg_key:`) runs after this and overrides with CPCB where available — preserving CPCB precedence. With no CPCB key it is skipped, leaving the rolling snapshots in place.
- The meta block then runs and stamps `refreshed_at` (so the footer reflects the 4h refresh) without changing `generated_today` (no new daily rows).

- [ ] **Step 3: Add the `aggregate` import if missing**

`run.py` already imports `from transform import aggregate, reconcile, storage` (added in the rollup work). Confirm with `grep -n "from transform import" pipeline/run.py`. If `aggregate` is absent, add it.

- [ ] **Step 4: Verify the suite + parse**

Run: `cd pipeline && .venv/bin/python -m pytest -q` (all pass), `.venv/bin/python -m ruff check run.py` (clean), `.venv/bin/python -c "import ast; ast.parse(open('run.py').read()); print('OK')"`.

- [ ] **Step 5: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(pipeline): hourly mode writes a rolling-24h live snapshot (OpenAQ)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Slow the hourly cron to every ~4h

**Files:**
- Modify: `.github/workflows/refresh-hourly.yml`

- [ ] **Step 1: Change the cron**

In `.github/workflows/refresh-hourly.yml`, change:
```yaml
    - cron: "17 * * * *" # hourly, offset off the top of the hour
```
to:
```yaml
    - cron: "17 */4 * * *" # every ~4h, offset off the top of the hour (rolling-24h headline)
```

- [ ] **Step 2: Sanity-check the file still parses as YAML**

Run: `cd "/Users/sarveshtewari/claude/AQI Dashboard" && python3 -c "import yaml; yaml.safe_load(open('.github/workflows/refresh-hourly.yml')); print('YAML OK')"`
Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/refresh-hourly.yml
git commit -m "ci: run refresh-hourly every ~4h (rolling-24h headline cadence)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `formatTimeIST` helper

**Files:**
- Modify: `web/src/lib/format.ts`

- [ ] **Step 1: Add the helper** (no web unit-test runner exists; correctness is verified in the preview in Task 6). Add to `web/src/lib/format.ts` after `formatDateTimeIST`:

```ts
// Time-only in IST, e.g. "14:00 IST" — used for the rolling-24h headline "as of" label.
export function formatTimeIST(iso: string): string {
  const time = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata",
  }).format(new Date(iso));
  return `${time} IST`;
}
```

- [ ] **Step 2: Type-check**

Run: `cd web && npx tsc --noEmit` → exit 0.

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/format.ts
git commit -m "feat(web): formatTimeIST helper for the rolling-24h 'as of' label

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Headline rolling-24h copy + tooltip

**Files:**
- Modify: `web/src/components/SectionTitle.tsx` (export `InfoDot`)
- Modify: `web/src/components/Headline.tsx`

- [ ] **Step 1: Export `InfoDot`**

In `web/src/components/SectionTitle.tsx`, change:
```tsx
function InfoDot({ children, label }: { children: ReactNode; label?: string }) {
```
to:
```tsx
export function InfoDot({ children, label }: { children: ReactNode; label?: string }) {
```

- [ ] **Step 2: Update imports in `Headline.tsx`**

At the top of `web/src/components/Headline.tsx`, add `formatTimeIST` to the format import and import `InfoDot`. The existing format import line is:
```tsx
import { formatDate, formatDateTimeIST } from "../lib/format";
```
Change to:
```tsx
import { formatDate, formatDateTimeIST, formatTimeIST } from "../lib/format";
import { InfoDot } from "./SectionTitle";
```

- [ ] **Step 3: Add the rolling-case computed values**

In `Headline.tsx`, just after the existing line `const sourceLabel = vm.source === "cpcb" ? "CPCB" : vm.source === "openaq" ? "OpenAQ" : null;`, add:

```tsx
  const isRolling = vm.live && vm.source === "openaq";
  const hoursAgo = vm.live && vm.updatedUtc
    ? Math.max(0, Math.round((Date.now() - new Date(vm.updatedUtc).getTime()) / 3.6e6))
    : null;
```

- [ ] **Step 4: Suppress the "delayed" notice for the rolling case**

In `Headline.tsx`, the `const notice =` expression currently reads:
```tsx
  const notice = veryStale
    ? `This city's monitor last reported a valid reading${updatedText ? ` on ${updatedText}` : ""} (${agoText(age!)}). Shown for reference only — it may not reflect current air quality.`
    : !vm.stale ? null
    : vm.live
      ? `Live reading may be delayed. Last updated ${updatedText ?? "recently"}.`
      : `Live data (CPCB) is currently unavailable, so this shows the latest published day${updatedText ? `, ${updatedText}` : ""}. History updates daily from OpenAQ.`;
```
Insert an `isRolling ? null :` branch right after the `veryStale` branch:
```tsx
  const notice = veryStale
    ? `This city's monitor last reported a valid reading${updatedText ? ` on ${updatedText}` : ""} (${agoText(age!)}). Shown for reference only — it may not reflect current air quality.`
    : isRolling ? null
    : !vm.stale ? null
    : vm.live
      ? `Live reading may be delayed. Last updated ${updatedText ?? "recently"}.`
      : `Live data (CPCB) is currently unavailable, so this shows the latest published day${updatedText ? `, ${updatedText}` : ""}. History updates daily from OpenAQ.`;
```
(Do not introduce an em-dash anywhere; the existing copy already uses one in the veryStale string — leave that line exactly as-is, do not add new ones.)

- [ ] **Step 5: Update the subtitle line + add the tooltip**

In `Headline.tsx`, replace the subtitle paragraph:
```tsx
          <p className="mt-2 text-xs text-muted">
            {vm.nStations > 0 ? `${vm.nStations} station${vm.nStations > 1 ? "s" : ""} · ` : ""}
            {sourceLabel ? `${sourceLabel} · ` : ""}
            {updatedText ? (vm.live ? `updated ${updatedText}` : `latest reading · ${updatedText}`) : (vm.live ? "live" : "latest available")}
            {age != null && age > 1 ? `, ${agoText(age)}` : ""}
          </p>
```
with:
```tsx
          <p className="mt-2 text-xs text-muted">
            {vm.nStations > 0 ? `${vm.nStations} station${vm.nStations > 1 ? "s" : ""} · ` : ""}
            {sourceLabel ? `${sourceLabel} · ` : ""}
            {!updatedText
              ? (vm.live ? "live" : "latest available")
              : isRolling
                ? `24h average · as of ${formatTimeIST(vm.updatedUtc!)}${hoursAgo != null ? `, ${hoursAgo}h ago` : ""}`
                : vm.live
                  ? `updated ${updatedText}`
                  : `latest reading · ${updatedText}${age != null && age > 1 ? `, ${agoText(age)}` : ""}`}
            {isRolling && (
              <span className="ml-1">
                <InfoDot label="How the headline reading is computed">
                  A rolling average of the last 24 hours of hourly readings (OpenAQ), labelled with the most recent hour. Updated every few hours.
                </InfoDot>
              </span>
            )}
          </p>
```

- [ ] **Step 6: Type-check**

Run: `cd web && npx tsc --noEmit` → exit 0. Then `cd web && npm run build` → succeeds.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/SectionTitle.tsx web/src/components/Headline.tsx
git commit -m "feat(web): rolling-24h headline copy + 'i' tooltip; drop 'delayed' notice

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Live verification

**Files:** none (verification only)

- [ ] **Step 1: Scoped local hourly run** (needs `../.env` with `OPENAQ_API_KEY`)

```bash
cd pipeline && .venv/bin/python run.py hourly --cities Delhi Mumbai --sensors first
```
Expected log: `[run] hourly scoped to N published cities`, `[run] hourly: fetching recent hourly…`, `[run] hourly: rolling-24h for N cities`, `[run] hourly: wrote N rolling live snapshots`.

- [ ] **Step 2: Inspect a written live snapshot**

```bash
cd pipeline && .venv/bin/python -c "import json; d=json.load(open('../data/live/delhi.json')); print('source=', d['source'], 'updated_utc=', d['updated_utc'], 'naqi=', d['aqi']['naqi']['index'])"
```
Expected: `source= openaq`, a recent `updated_utc` (within the last day or two of available hourly), and a numeric NAQI index.

- [ ] **Step 3: Preview the headline**

`preview_start` the `web` server, load Delhi, and confirm the headline subtitle shows `… · OpenAQ · 24h average · as of HH:MM IST, Nh ago`, the "i" tooltip renders the rolling explanation, and the "Live data (CPCB) is currently unavailable…" banner is gone. Check `preview_console_logs` for errors.

- [ ] **Step 4: Push + open PR**

```bash
cd "/Users/sarveshtewari/claude/AQI Dashboard"
git push -u origin feat/rolling-24h-headline
gh pr create --fill --title "Rolling-24h headline from OpenAQ hourly (#5)"
```

- [ ] **Step 5: After merge — trigger one hourly run to populate live across all cities**

```bash
gh workflow run refresh-hourly.yml
```
Then confirm the live site headline shows a rolling reading for a well-covered city.

---

## Self-review

- **Spec coverage:** rolling-24h compute (Task 1) ✓; hourly-mode rework + CPCB precedence + recent-tier persist (Task 2) ✓; ≥12h coverage via `AIRATLAS_MIN_ROLLING_HOURS` default 12 (Task 1/2) ✓; every-4h cron (Task 3) ✓; subtitle option A + time-only IST (Tasks 4, 5) ✓; drop CPCB-unavailable banner when rolling (Task 5) ✓; InfoDot tooltip via exported helper (Task 5) ✓; fallback ladder = existing live→daily frontend logic (unchanged, noted) ✓; data contract unchanged (live_snapshot shape) ✓.
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type/name consistency:** `rolling_24h(hourly, *, min_hours, window_hours)`, `formatTimeIST(iso)`, `InfoDot` (exported), `isRolling`/`hoursAgo` used consistently across tasks.
- **Note:** frontend has no unit-test runner, so Tasks 4-5 verify via `tsc` + `npm run build` + the preview in Task 6 — consistent with the codebase.
