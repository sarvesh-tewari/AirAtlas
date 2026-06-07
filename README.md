# AirAtlas — India Air Quality + Weather Dashboard

A free, open-source, public dashboard for Indian cities showing **air quality (AQI)**
and **weather**, with multi-year seasonal trends, severity at a glance,
pollution-vs-weather correlation, and city-to-city comparison.

The default AQI standard is **India's NAQI**, with a user toggle to **US EPA AQI**
and **EU EAQI** — all computed from raw pollutant concentrations, so identical air
can be compared across standards.

> **Status:** 🚧 In active build. Live link will be added here at launch.

---

## Why this exists

AQI is a *formula, not a measurement*. The same air reads "Moderate" under India's
NAQI but "Unhealthy" under the US EPA standard, because the breakpoint tables differ.
AirAtlas stores **raw pollutant concentrations** and computes any standard on demand,
making those differences transparent for a policy and public audience.

## Methodology (summary)

- **Today's headline** comes from **CPCB** (official, via data.gov.in).
- **History (up to and including yesterday)** comes from **OpenAQ**, which re-ingests
  the same CPCB stations and keeps multi-year history.
- **Weather** (current + historical) comes from **Open-Meteo**.
- The today/history seam is rendered cleanly and labelled, so the live CPCB number and
  the OpenAQ history never visibly contradict each other.
- AQI for all three standards is computed in `pipeline/aqi/` from raw concentrations,
  respecting each standard's averaging windows and breakpoint tables.

Full methodology, breakpoint versions, and the source reconciliation rule live on the
**About / Methodology** page and in [`SOURCES.md`](SOURCES.md).

## Architecture

Static site + scheduled data pipeline — no always-on server.

- **Pipeline (Python):** fetch → compute AQI → aggregate → reconcile → write Parquet/JSON.
  Runs on GitHub Actions cron (hourly live + daily history).
- **Data:** two-tier Parquet (multi-year daily + last ~90 days hourly) plus a small live
  JSON snapshot, committed to the repo. **The published Parquet files _are_ the open dataset.**
- **Frontend:** React + Vite + TypeScript, querying the Parquet **in-browser via DuckDB-WASM**.
  Charts with Apache ECharts; map with Leaflet.
- **Hosting:** GitHub Pages (with a clean migration path to Cloudflare Pages).

See [`docs/`](docs/) for the full build plan and setup checklist.

## Repository layout

```
pipeline/   Python data pipeline: AQI engine, ingestion, transform, orchestration
data/       Published data — live/ (JSON), history/ + recent/ (Parquet), meta/
web/        React + Vite + TypeScript frontend
.github/    Scheduled refresh + deploy workflows
docs/        Build plan + setup checklist
```

## Local development

Prerequisites: Python 3.11+, Node.js 20+, Git. (See [`docs/SETUP.md`](docs/SETUP.md).)

```bash
# Pipeline
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest                      # run the AQI engine tests

# Frontend (added in a later phase)
cd ../web
npm install
npm run dev
```

Copy `.env.example` to `.env` and add your API keys for local pipeline runs.
**Never commit real keys.**

## Licensing

- **Code:** [MIT](LICENSE)
- **Data:** [CC BY 4.0](LICENSE-DATA) — attribute CPCB / data.gov.in, OpenAQ, and Open-Meteo.

## Acknowledgements

Air-quality data © CPCB / data.gov.in and OpenAQ (CC BY); weather data © Open-Meteo
(CC BY 4.0).
