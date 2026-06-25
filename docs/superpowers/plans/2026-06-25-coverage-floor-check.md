# Daily coverage-floor check — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alert when a daily refresh succeeds but publishes far fewer cities/stations than the previous run (a silent partial outage).

**Architecture:** Extend `pipeline/checks.py` into a two-subcommand CLI (`staleness`, `coverage`). The coverage check compares the just-built `data/meta` counts against a snapshot of the previously-published meta (captured by the workflow right after hydrate, before the pipeline overwrites it). It runs in `refresh-daily.yml` after the refresh and before publish, so a sharp drop fails the run, skips publish (keeping the prior good data), and fires the existing failure-issue alert.

**Tech Stack:** Python 3.13, argparse, pytest, ruff. GitHub Actions YAML. Run pipeline tests from `pipeline/` via `.venv/bin/python -m pytest`.

## Global Constraints
- No em-dashes in any copy/log strings (use hyphens or commas).
- ruff line-length 100; match existing `pipeline/` style.
- The two subcommands ship together with the workflow updates on one branch (converting to subcommands changes the existing `refresh-hourly` call, so they are coupled and merge atomically).

**Spec:** `docs/superpowers/specs/2026-06-25-coverage-floor-check-design.md`
**Branch:** `feat/coverage-floor-check` (already created; spec committed)

---

## Task 1: Coverage logic + subcommand CLI in checks.py

**Files:**
- Modify: `pipeline/checks.py`
- Test: `pipeline/test_checks.py`

**Interfaces:**
- Produces:
  - `read_coverage(meta_dir) -> tuple[int | None, int | None]` — (city_count, total_stations); each is None if its file is missing/unreadable.
  - `coverage_verdict(prior_cities, current_cities, prior_stations, current_stations, max_city_drop=0.05, max_station_drop=0.10) -> tuple[bool, str]` — (ok, message). Pure.
  - CLI: `checks.py staleness --live-dir <dir> --max-hours <n>` and `checks.py coverage --baseline <dir> --current <dir> --max-city-drop <f> --max-station-drop <f>`.
- Consumes: nothing new (existing `newest_live_age_hours` is unchanged).

- [ ] **Step 1: Write the failing tests** — append to `pipeline/test_checks.py`:

```python
def test_coverage_verdict_ok_when_stable():
    ok, msg = checks.coverage_verdict(286, 286, 467, 467)
    assert ok is True
    assert msg.startswith("OK:")


def test_coverage_verdict_city_drop_over_5pct_trips():
    ok, msg = checks.coverage_verdict(286, 240, 467, 467)  # cities -16%
    assert ok is False
    assert "COVERAGE DROP" in msg and "cities" in msg


def test_coverage_verdict_city_drop_under_5pct_ok():
    ok, _ = checks.coverage_verdict(286, 276, 467, 467)  # cities -3.5%
    assert ok is True


def test_coverage_verdict_station_drop_over_10pct_trips():
    ok, msg = checks.coverage_verdict(286, 286, 467, 400)  # stations -14%
    assert ok is False
    assert "stations" in msg


def test_coverage_verdict_per_metric_thresholds():
    # a 6% drop trips cities (>5%) but NOT stations (<10%)
    ok_city, msg_city = checks.coverage_verdict(100, 94, 100, 100)
    ok_st, _ = checks.coverage_verdict(100, 100, 100, 94)
    assert ok_city is False and "cities" in msg_city and "stations" not in msg_city
    assert ok_st is True


def test_coverage_verdict_growth_never_trips():
    ok, _ = checks.coverage_verdict(286, 300, 467, 480)
    assert ok is True


def test_coverage_verdict_zero_prior_skips_metric():
    # no divide-by-zero; a None/0 prior means that metric is not evaluated
    ok, _ = checks.coverage_verdict(0, 50, None, 50)
    assert ok is True


def test_read_coverage(tmp_path):
    (tmp_path / "city_list.json").write_text(json.dumps({"cities": ["a", "b", "c"]}))
    (tmp_path / "cities.json").write_text(json.dumps([{"n_stations": 2}, {"n_stations": 3}]))
    assert checks.read_coverage(tmp_path) == (3, 5)


def test_read_coverage_missing_files(tmp_path):
    assert checks.read_coverage(tmp_path) == (None, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline && .venv/bin/python -m pytest test_checks.py -k "coverage or read_coverage" -v`
Expected: FAIL — `module 'checks' has no attribute 'coverage_verdict'` / `read_coverage`.

- [ ] **Step 3: Implement** — edit `pipeline/checks.py`. Add these functions after `newest_live_age_hours`:

```python
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
```

Then refactor `main()` into subcommands. Replace the existing `main()` with:

```python
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
```

(Note the existing staleness "skipping" message had an em-dash; this rewrite uses a hyphen, satisfying the no-em-dash rule.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && .venv/bin/python -m pytest test_checks.py -v` (all pass, incl. the 3 pre-existing).
Then ruff: `cd pipeline && .venv/bin/python -m ruff check checks.py test_checks.py` (clean).

- [ ] **Step 5: Smoke-test both CLIs locally**

```bash
cd pipeline
mkdir -p /tmp/cov-a /tmp/cov-b
printf '{"cities":["a","b","c","d"]}' > /tmp/cov-a/city_list.json
printf '[{"n_stations":5},{"n_stations":5}]' > /tmp/cov-a/cities.json
printf '{"cities":["a","b"]}' > /tmp/cov-b/city_list.json
printf '[{"n_stations":5}]' > /tmp/cov-b/cities.json
.venv/bin/python checks.py coverage --baseline /tmp/cov-a --current /tmp/cov-b; echo "exit=$?"   # expect COVERAGE DROP + exit 1
.venv/bin/python checks.py coverage --baseline /tmp/cov-a --current /tmp/cov-a; echo "exit=$?"   # expect OK + exit 0
mkdir -p /tmp/live && printf '{"updated_utc":"2020-01-01T00:00:00Z"}' > /tmp/live/x.json
.venv/bin/python checks.py staleness --live-dir /tmp/live --max-hours 96; echo "exit=$?"         # expect STALE + exit 1
```
Expected: the coverage drop prints `COVERAGE DROP: cities 4 -> 2 (50% > 5%); stations 10 -> 5 (50% > 10%)` and exits 1; the equal dirs print `OK:` and exit 0; staleness still works under the subcommand.

- [ ] **Step 6: Commit**

```bash
git add pipeline/checks.py pipeline/test_checks.py
git commit -m "feat(pipeline): coverage-floor check + subcommand CLI in checks.py

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Wire the check into the workflows

**Files:**
- Modify: `.github/workflows/refresh-daily.yml` (capture baseline + coverage step)
- Modify: `.github/workflows/refresh-hourly.yml` (staleness subcommand)

**Interfaces:**
- Consumes: `checks.py staleness …` and `checks.py coverage …` from Task 1.

- [ ] **Step 1: Update the refresh-hourly staleness call**

In `.github/workflows/refresh-hourly.yml`, change the staleness command from:
```yaml
          python pipeline/checks.py --live-dir data/live --max-hours 96 2>&1 | tee -a /tmp/airatlas-run.log
```
to:
```yaml
          python pipeline/checks.py staleness --live-dir data/live --max-hours 96 2>&1 | tee -a /tmp/airatlas-run.log
```

- [ ] **Step 2: Capture the coverage baseline in refresh-daily (after Hydrate)**

In `.github/workflows/refresh-daily.yml`, add a new step immediately AFTER the `Hydrate prior data from data branch` step and BEFORE the `Refresh history + recent (+ live)` step:

```yaml
      - name: Capture coverage baseline
        run: |
          mkdir -p /tmp/coverage-baseline
          cp data/meta/city_list.json data/meta/cities.json /tmp/coverage-baseline/ 2>/dev/null \
            && echo "Captured coverage baseline." \
            || echo "No prior meta to baseline (first run)."
```

- [ ] **Step 3: Add the coverage-floor check (after Refresh, before Publish)**

In `.github/workflows/refresh-daily.yml`, add a new step immediately AFTER the `Refresh history + recent (+ live)` step and BEFORE the `Publish data to data branch` step:

```yaml
      # Fail (and alert) BEFORE publishing if this refresh produced far fewer cities/stations than
      # the previous run, so we keep the prior good data instead of overwriting it with a thin set.
      - name: Coverage-floor check
        run: |
          set -o pipefail
          python pipeline/checks.py coverage \
            --baseline /tmp/coverage-baseline --current data/meta \
            --max-city-drop 0.05 --max-station-drop 0.10 2>&1 | tee -a /tmp/airatlas-run.log
```

- [ ] **Step 4: Validate the YAML**

```bash
cd "/Users/sarveshtewari/claude/AQI Dashboard"
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/refresh-daily.yml')); yaml.safe_load(open('.github/workflows/refresh-hourly.yml')); print('YAML OK')"
```
Expected: `YAML OK`. Also confirm step order with:
`grep -nE 'name: (Hydrate|Capture coverage|Refresh history|Coverage-floor|Publish)' .github/workflows/refresh-daily.yml` — order must be Hydrate -> Capture coverage baseline -> Refresh -> Coverage-floor check -> Publish.

- [ ] **Step 5: Confirm the full suite still passes**

`cd pipeline && .venv/bin/python -m pytest -q` (all pass) and `.venv/bin/python -m ruff check .` (clean).

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/refresh-daily.yml .github/workflows/refresh-hourly.yml
git commit -m "ci: coverage-floor check in refresh-daily; staleness subcommand in refresh-hourly

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Verify against real published meta

**Files:** none (verification only)

- [ ] **Step 1: Run the coverage check against the live data branch**

```bash
cd "/Users/sarveshtewari/claude/AQI Dashboard"
git fetch origin data --quiet
rm -rf /tmp/realmeta && mkdir -p /tmp/realmeta/meta
git archive origin/data data/meta | tar -x -C /tmp/realmeta --strip-components=1
# baseline == current (same published meta) -> should be OK
cd pipeline && .venv/bin/python checks.py coverage --baseline /tmp/realmeta/meta --current /tmp/realmeta/meta; echo "exit=$?"
```
Expected: `OK: coverage cities 286 (prior 286), stations 467 (prior 467)`, exit 0.

- [ ] **Step 2: Simulate a drop**

```bash
cd "/Users/sarveshtewari/claude/AQI Dashboard"
rm -rf /tmp/thin && cp -r /tmp/realmeta/meta /tmp/thin
python3 -c "import json; p='/tmp/thin/city_list.json'; d=json.load(open(p)); d['cities']=d['cities'][:200]; json.dump(d, open(p,'w'))"
cd pipeline && .venv/bin/python checks.py coverage --baseline /tmp/realmeta/meta --current /tmp/thin; echo "exit=$?"
```
Expected: `COVERAGE DROP: cities 286 -> 200 (30% > 5%)`, exit 1.

- [ ] **Step 3: Push + open PR (CI runs ruff + pytest + web build)**

```bash
cd "/Users/sarveshtewari/claude/AQI Dashboard"
git push -u origin feat/coverage-floor-check
gh pr create --fill --title "Daily coverage-floor health check (#11)"
```

---

## Self-review

- **Spec coverage:** metric = city count + total stations (Task 1 `read_coverage`) ✓; baseline A via workflow snapshot after hydrate (Task 2 Step 2) ✓; thresholds city 5% / station 10% (Task 1 defaults + Task 2 Step 3 flags) ✓; placement after refresh / before publish, fail keeps prior data + existing alert (Task 2 Step 3 + comment) ✓; subcommands + refresh-hourly update (Task 1 + Task 2 Step 1) ✓; edge cases no-baseline/zero-prior/growth (Task 1 tests + `_run_coverage` skip) ✓; pure comparator unit-tested (Task 1) ✓.
- **Placeholder scan:** none — all steps have concrete code + commands + expected output.
- **Type/name consistency:** `read_coverage -> (int|None, int|None)`, `coverage_verdict(...) -> (bool, str)`, subcommands `staleness`/`coverage` used identically in Task 1 and Task 2.
- **No em-dashes:** all new strings use hyphens (including the rewritten staleness "skipping" message).
