# SOURCES.md — data sources, terms, cadence & data dictionary

This file is the authoritative record of where AirAtlas's data comes from, under what
terms, how often it refreshes, and what every published column means. Pin exact
breakpoint/standard versions here so the methodology is reproducible.

> Items marked _(TBC at implementation)_ are filled in during the phase that builds them.

---

## 1. Sources

### Live AQI (today) — CPCB via data.gov.in
- **Resource:** "Real time Air Quality Index from various locations"
- **URL:** https://data.gov.in/ (resource page) _(exact resource URL: TBC at implementation)_
- **Auth:** Free API key (`DATA_GOV_IN_KEY`)
- **Role:** Official current headline + raw per-pollutant concentrations for today.
- **Licence / attribution:** Government of India / CPCB — attribute.
- **Refresh cadence:** Hourly (GitHub Actions `refresh-hourly.yml`).

### Historical AQI (multi-year) — OpenAQ
- **URL:** https://docs.openaq.org (API v3) + AWS S3 open-data archive
- **Auth:** Free API key (`OPENAQ_API_KEY`)
- **Role:** Backfilled multi-year trends; re-ingests the same CPCB Indian stations.
- **Licence / attribution:** CC BY; comply with upstream terms — attribute.
- **Refresh cadence:** Daily delta (GitHub Actions `refresh-daily.yml`).

### Weather (current + historical) — Open-Meteo
- **URL:** https://open-meteo.com (Forecast API + Archive/ERA5 API, history to 1940)
- **Auth:** None.
- **Role:** Temperature, humidity, rainfall, wind — current and multi-year.
- **Licence / attribution:** CC BY 4.0 — attribute.
- **Refresh cadence:** Current = hourly; archive delta = daily.

---

## 2. Source reconciliation rule

To avoid a visible contradiction between CPCB and OpenAQ for the same hour:

- **Today** → CPCB.
- **Up to and including yesterday** → OpenAQ.
- Every view labels its source; the today/history seam is rendered with no overlap.

---

## 3. AQI standard versions (pin exact versions here)

| Standard | Version / date | Source | Notes |
|---|---|---|---|
| India NAQI | CPCB 2014 | CPCB | 8 pollutants; overall = max sub-index. |
| US EPA AQI | Effective 2024-05-06 | EPA AQS code table + May 2024 AQI TAD (airnow.gov) | Gas tables _(TBC at implementation)_. |
| EU EAQI | EEA 2024 revision | airindex.eea.europa.eu | 6-band; numeric bands _(TBC at implementation)_. |

Breakpoint tables live in `pipeline/aqi/breakpoints.py`. When a standard is revised,
update that module + its tests and bump the version row above.

---

## 4. Coverage report

OpenAQ depth/completeness varies by station. The build generates a coverage report at
`data/meta/coverage.*` listing, per target city, the available date range and
completeness, and flagging thin cities. _(Generated in the Storage phase.)_

---

## 5. Data dictionary

Describes every published column and unit. _(Filled in during the Storage phase.)_

### `data/live/<city>.json` — current snapshot _(TBC)_
| Field | Type | Unit | Description |
|---|---|---|---|
| _TBC_ | | | |

### `data/history/<city>.parquet` — multi-year daily _(TBC)_
| Column | Type | Unit | Description |
|---|---|---|---|
| _TBC_ | | | |

### `data/recent/<city>.parquet` — last ~90 days hourly _(TBC)_
| Column | Type | Unit | Description |
|---|---|---|---|
| _TBC_ | | | |

### `data/meta/` — city list, station map, coverage report _(TBC)_
| File | Description |
|---|---|
| _TBC_ | |

---

## 6. Units convention

- Concentrations stored in **µg/m³**, except **CO in mg/m³** (source units preserved).
- US EPA gas sub-indices require **ppb/ppm**; conversion happens in the AQI engine, not
  in storage. Stored values remain in source units.
