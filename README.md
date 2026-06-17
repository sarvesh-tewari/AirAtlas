# AirAtlas — India Air Quality + Weather Dashboard

[**Live site → sarvesh-tewari.github.io/AirAtlas**](https://sarvesh-tewari.github.io/AirAtlas/)

A free, open-source, public dashboard for Indian cities showing **air quality (AQI)**
and **weather**, with multi-year seasonal trends, severity at a glance,
pollution-vs-weather correlation, and city-to-city comparison.

The default AQI standard is **India's NAQI**, with a user toggle to **US EPA AQI**
and **EU EAQI** — all computed from raw pollutant concentrations, so identical air
can be compared across standards.

---

## Why this exists

AQI is a *formula, not a measurement*. The same air reads "Moderate" under India's
NAQI but "Unhealthy" under the US EPA standard, because the breakpoint tables differ.
AirAtlas stores **raw pollutant concentrations** and computes any standard on demand,
making those differences transparent for a policy and public audience.

## What you can do

- See the current AQI for **285+ Indian cities** (geolocates to your nearest covered city).
- Toggle between **NAQI, US EPA, and EU EAQI** and watch the same air re-classify.
- Explore **multi-year daily history** — seasonal trends, monthly heatmaps, year-by-year summaries.
- Break the index down into its **individual pollutants** (PM2.5, PM10, NO2, SO2, CO, O3, NH3).
- See **how many days each year** breached each category, and **how weather tracks pollution**.
- **Compare cities** side by side.

## Methodology (summary)

- **Air quality** comes from **CPCB monitoring stations** (Central Pollution Control Board),
  sourced via **OpenAQ**, which keeps multi-year history of the same stations. The headline
  shows the latest available reading and refreshes daily, so it can lag by about a day.
- **Weather** (current + historical) comes from **Open-Meteo**.
- AQI for all three standards is computed in `pipeline/aqi/` from raw concentrations,
  respecting each standard's averaging windows and breakpoint tables.
- A city's value is the **mean pollutant concentration across its stations**, computed
  identically for every standard so the comparison is apples-to-apples.

Full methodology, breakpoint versions, and the source reconciliation rule live on the
**About** page in the app and in [`SOURCES.md`](SOURCES.md).

## Architecture

Static site + scheduled data pipeline — no always-on server.

- **Pipeline (Python):** fetch → compute AQI → aggregate → reconcile → write Parquet/JSON.
  Runs on GitHub Actions cron (hourly live + daily history).
- **Data:** two-tier Parquet (multi-year daily + last ~90 days hourly) plus a small live
  JSON snapshot. **The published Parquet files _are_ the open dataset.**
- **Frontend:** React + Vite + TypeScript, querying the Parquet **in-browser via DuckDB-WASM**.
  Charts with Apache ECharts; map with Leaflet.
- **Hosting:** GitHub Pages.

## Repository layout

```
pipeline/   Python data pipeline: AQI engine, ingestion, transform, orchestration
data/       Published data — live/ (JSON), history/ + recent/ (Parquet), meta/
web/        React + Vite + TypeScript frontend
.github/    Scheduled refresh + deploy workflows
```

## Local development

Prerequisites: Python 3.11+, Node.js 22+, Git.

```bash
# Pipeline
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # run the pipeline + AQI engine tests

# Frontend
cd ../web
npm install
npm run dev
```

Copy `.env.example` to `.env` and add your API keys for local pipeline runs.
**Never commit real keys.**

## Contributing

Contributions, bug reports, and data-accuracy feedback are welcome, all through GitHub.

- Found a problem or a reading that looks wrong? [Open an issue.](https://github.com/sarvesh-tewari/AirAtlas/issues/new/choose)
- Want to help? Browse the [open backlog](https://github.com/sarvesh-tewari/AirAtlas/issues), especially [`good first issue`](https://github.com/sarvesh-tewari/AirAtlas/labels/good%20first%20issue) and [`help wanted`](https://github.com/sarvesh-tewari/AirAtlas/labels/help%20wanted), then open a pull request.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, the checks to run before a PR, and conventions.

## Licensing

- **Code:** [MIT](LICENSE)
- **Data:** [CC BY 4.0](LICENSE-DATA) — attribute CPCB, OpenAQ, and Open-Meteo.

## Acknowledgements

Air-quality data © CPCB (Central Pollution Control Board), distributed via OpenAQ
(CC BY); weather data © Open-Meteo (CC BY 4.0).
