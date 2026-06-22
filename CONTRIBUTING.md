# Contributing to AirAtlas

Thanks for your interest. AirAtlas is a free, open-source dashboard of India air quality (AQI) and
weather. Bug reports, data-accuracy feedback, and code contributions are all welcome, and all of it
happens through GitHub: **issues** for feedback and bugs, **pull requests** for changes.

## Ways to contribute

- **Report a problem or a reading that looks wrong** - open an issue using one of the
  [issue templates](https://github.com/sarvesh-tewari/AirAtlas/issues/new/choose).
- **Pick up backlog work** - browse the [open issues](https://github.com/sarvesh-tewari/AirAtlas/issues),
  especially ones labelled [`good first issue`](https://github.com/sarvesh-tewari/AirAtlas/labels/good%20first%20issue)
  and [`help wanted`](https://github.com/sarvesh-tewari/AirAtlas/labels/help%20wanted). Comment on an
  issue to claim it before you start, so we don't duplicate effort.
- **Submit a fix or feature** - open a pull request (see below).

## Project layout

- `pipeline/` - Python data pipeline: ingestion, the AQI engine, transforms, orchestration.
- `web/` - React + Vite + TypeScript dashboard; reads the published data in-browser via DuckDB-WASM.
- `.github/workflows/` - scheduled data refresh, deploy, and the smoke/uptime checks.
- Published data lives on the orphan `data` branch, not on `main` (`main` keeps only `.gitkeep`
  placeholders under `data/`). You do not need the dataset to work on most things; the frontend
  falls back to empty states, and the pipeline has its own fixtures/tests.

## Local setup

```bash
# Pipeline (Python 3.11+)
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                 # run the test suite

# Frontend (Node.js 22+)
cd ../web
npm install
npm run dev               # local dev server
```

Copy `.env.example` to `.env` for local pipeline runs that hit the APIs. **Never commit real keys.**

## Before you open a pull request

CI runs the same checks automatically on every PR (no approval needed to see the results), so run
them locally first:

- **Python:** `ruff check pipeline` and `cd pipeline && pytest -q`
- **Web:** `cd web && npm run format` (auto-formats), then `npm run build` (type-checks and bundles)

Also:

- Add or update tests for any behaviour change. The pipeline is developed test-first.
- Keep each PR focused on one thing, and describe **what** changed and **why**.
- Branch from `main` and open the PR against `main`.

## Style and conventions

- **Python:** follow `ruff` (config lives in `pipeline/`); match the surrounding code.
- **TypeScript/React:** formatting is handled by **Prettier** (config in `web/.prettierrc.json`).
  Run `npm run format` before committing; CI runs `npm run format:check` and will fail on unformatted
  code. Let Prettier handle layout rather than hand-formatting, and don't reformat lines unrelated to
  your change. Follow the existing component patterns; it must also pass `npm run build`.
- **Copy / UI:** no em-dashes in user-facing copy (use commas or hyphens). Any rule that changes
  what data is shown or how (filtering, fading, capping, approximating) should be explained on the
  site (the About page or inline), so users understand what they are looking at.
- **AQI methodology** is documented on the About page and in [`SOURCES.md`](SOURCES.md); update both
  if you change a standard, breakpoint, or aggregation rule.

## Reporting a reading that looks wrong

Use the **Data accuracy** issue template and include: the city, the value AirAtlas shows, what you
expected and your source, and a screenshot if possible. A few things that are working as intended:

- AQI is a *calculated index*, not a measurement, and differs by standard (NAQI / US / EU) for the
  same air.
- Data can lag about 1-2 days by nature (the live CPCB source is often unavailable).
- A city whose monitor has gone quiet is shown muted and clearly dated, not as current.

## License

By contributing, you agree that your contributions are licensed under the project's terms:
**MIT** for code and **CC BY 4.0** for data.
