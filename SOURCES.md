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

## 3. AQI standard versions (pinned)

| Standard | Version / date | Source (verified 2026-06-08) | Notes |
|---|---|---|---|
| India NAQI | CPCB 2014 | CPCB National Air Quality Index | 8 pollutants (PM2.5, PM10, NO2, SO2, O3, CO, NH3, Pb); overall = max sub-index. |
| US EPA AQI | Effective 2024-05-06 | EPA AQS breakpoints code table (`aqs.epa.gov/aqsweb/documents/codetables/aqi_breakpoints.html`) | 6 pollutants; gases in ppb/ppm; PM2.5 May-2024 revision. |
| EU EAQI | EEA 2024 revision | `airindex.eea.europa.eu` + ETC HE Report 2024-17; cross-checked vs `aqihub.info/indices/eu` | 6-band; aligned to WHO 2021 guidelines. **Supersedes pre-2024 bands.** |

Breakpoint tables live in `pipeline/aqi/breakpoints.py` (verified data, fully unit-tested
incl. the §7 three-standard regression). When a standard is revised, update that module +
its tests and bump the version row above.

### Encoded decisions (for reproducibility)

- **NAQI top-of-scale:** CPCB leaves the 401–500 ("Severe") band open-topped. Segments are
  encoded with closed bounds through the 301–400 band; any concentration above the top
  closed breakpoint returns **AQI 500 flagged `off_scale`**. The whole 401–500 range is one
  category ("Severe") so policy messaging is unaffected.
- **EU EAQI bands (current, µg/m³)** — upper-bound inclusive:
  | Band | PM2.5 | PM10 | NO2 | O3 | SO2 |
  |---|---|---|---|---|---|
  | Good | 0–5 | 0–15 | 0–10 | 0–60 | 0–20 |
  | Fair | 6–15 | 16–45 | 11–25 | 61–100 | 21–40 |
  | Moderate | 16–50 | 46–120 | 26–60 | 101–120 | 41–125 |
  | Poor | 51–90 | 121–195 | 61–100 | 121–160 | 126–190 |
  | Very Poor | 91–140 | 196–270 | 101–150 | 161–180 | 191–275 |
  | Extremely Poor | >140 | >270 | >150 | >180 | >275 |
  Averaging: **PM2.5/PM10 = 24h running mean; NO2/O3/SO2 = hourly** (per current EEA
  methodology — corrects the build plan's §6 "all hourly" note).
- **µg/m³ → ppb/ppm conversion (US gases):** `ppb = C(µg/m³) × 24.45 / MW` at 25 °C, 1 atm.
  MW: NO2 46.0055, SO2 64.066, O3 48.00, CO 28.010. CO is stored in mg/m³ → ppm directly.
- **Plan §7 EU expectation corrected:** the build plan said the §7 case reads "Extremely
  Poor" under EU — that reflected the pre-2024 bands. Under the current bands it is
  **"Very Poor" (dominant PM10)**. The regression test asserts the correct current value.
- **Pb (NAQI 8th pollutant):** breakpoints are encoded, but Pb is rarely present in the live
  CPCB / OpenAQ feeds; it is simply omitted from the overall index when absent.

---

## 4. Coverage report

OpenAQ depth/completeness varies by station. The build generates a coverage report at
`data/meta/coverage.*` listing, per target city, the available date range and
completeness, and flagging thin cities. _(Generated in the Storage phase.)_

---

## 5. Data dictionary

Describes every published column and unit. Files are keyed by a city **slug**
(lowercased, non-alphanumerics → `-`). Concentrations are µg/m³ except **CO in mg/m³**.

### `data/history/<city-slug>.parquet` — one row per city per DAY
| Column | Type | Unit | Description |
|---|---|---|---|
| `city` | str | — | City name (CPCB label) |
| `date` | str | — | Local calendar date `YYYY-MM-DD` |
| `source` | str | — | `cpcb` (today) or `openaq` (history) |
| `n_stations` | int | — | Stations contributing that day |
| `pm25`,`pm10`,`no2`,`so2`,`o3`,`co`,`nh3` | float? | µg/m³ (CO mg/m³) | City-mean concentrations (null if absent) |
| `aqi_naqi` | int? | index | NAQI 0–500 (null if <3 pollutants) |
| `naqi_category` | str? | — | Good…Severe |
| `naqi_dominant` | str? | — | Comma-sep dominant pollutant(s) |
| `aqi_us` | int? | index | US EPA AQI 0–500 |
| `us_category`,`us_dominant` | str? | — | US category / dominant |
| `eu_band` | str? | — | EU EAQI band (Good…Extremely Poor) |
| `eu_dominant` | str? | — | EU dominant pollutant(s) |
| `temp_c`,`temp_min_c`,`temp_max_c` | float? | °C | Daily mean/min/max temperature |
| `rh_pct` | float? | % | Daily mean relative humidity |
| `precip_mm` | float? | mm | Daily precipitation sum |
| `wind_ms` | float? | m/s | Daily max wind speed |

### `data/recent/<city-slug>.parquet` — one row per city per HOUR (last ~90 days)
| Column | Type | Unit | Description |
|---|---|---|---|
| `city` | str | — | City name |
| `datetime_utc` | str | — | Hour instant, ISO-8601 Z |
| `source` | str | — | `openaq` |
| `pm25`,`pm10`,`no2`,`so2`,`o3`,`co`,`nh3` | float? | µg/m³ (CO mg/m³) | City-mean hourly concentrations |
| `temp_c`,`rh_pct`,`precip_mm`,`wind_ms` | float? | — | Hourly weather (when available) |

No per-hour AQI: AQI requires a 24h window, so AQI lives in the daily file.

### `data/live/<city-slug>.json` — today's snapshot
| Field | Type | Description |
|---|---|---|
| `city`,`source`,`updated_utc`,`n_stations` | — | Identity + freshness (source = `cpcb`) |
| `pollutants.<p>.value` / `.unit` | float / str | Current concentration + unit |
| `pollutants.<p>.naqi_subindex` / `.us_subindex` | int | Per-pollutant sub-index |
| `aqi.naqi` / `aqi.us` / `aqi.eu` | obj | `{index|band, category, dominant[], valid}` per standard |
| `weather` | obj? | `{temp_c, rh_pct, precip_mm, wind_ms, wind_dir_deg}` |

### `data/meta/`
| File | Description |
|---|---|
| `city_list.json` | Cities present + generation date |
| `station_city_map.json` | Resolved `station_id → city` |
| `unmapped_stations.json` | Station ids whose city couldn't be parsed (need an override) |
| `coverage.json` | Per city: `n_days`, `first_date`, `last_date`, `thin` flag (the §2 thin-city caveat) |
| `station_city_overrides.json` | _(optional, manual)_ `station_id → city` overrides |
| `city_aliases.json` | _(optional, manual)_ city-name aliases, e.g. `{"New Delhi": "Delhi"}` |

---

## 6. Units convention

- Concentrations are normalized at **ingestion** to **µg/m³**, except **CO in mg/m³**.
- Some sources report gases in **ppb** (e.g. OpenAQ's modern CPCB sensors report NO2/SO2/CO
  in ppb). These are converted ppb → µg/m³ at ingestion using `ppb × MW / 24.45` (25 °C,
  1 atm) so storage is single-unit. The US EPA engine then converts µg/m³ → ppb internally
  for its own sub-index lookup — the two conversions are independent and intentional.

---

## 7. Ingestion notes (verified at build, 2026-06-11)

- **OpenAQ v3:** CPCB stations live under **provider id 168**. A station's multi-year series
  for one pollutant can be **split across several sensor ids** over time (and stations carry
  duplicate sensors per pollutant, some ppb / some µg/m³) — history fetch unions all
  same-parameter sensors at a location. Aggregate endpoints (`/sensors/{id}/days`, `/hours`)
  filter on **`date_from`/`date_to`** (date-only); only raw `/measurements` uses
  `datetime_from`/`datetime_to`. Daily records key on the **local calendar date**.
- **Open-Meteo:** Forecast API (`current` + `hourly`) and Archive/ERA5 (`daily`); no key.
  Wind requested as `wind_speed_unit=ms`; parser also converts km/h→m/s defensively.
- **CPCB / data.gov.in:** resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69`. Two field-name
  variants exist (`pollutant_avg`/… vs `avg_value`/… + `latitude`); the parser handles both.
  Missing values are the string `"NA"`. `last_update` is **IST** → converted to UTC.
  **⚠ Live verification pending:** data.gov.in was returning 502/timeouts during the build,
  so `cpcb.py` is tested against a fixture mirroring the documented schema; re-verify against
  the live API once it recovers (`cpcb.fetch_live(<key>)`).
- HTTP layer (`ingest/http.py`): disk cache in `pipeline/.cache/` (gitignored; api-key
  stripped from cache keys), retry/backoff on 5xx/timeouts, immediate raise on 4xx.
- **Plausibility QA (`transform/aggregate.drop_implausible`):** sensor-error outliers are
  dropped before city aggregation — values outside per-pollutant physical bounds (e.g. SO2
  > 2000, PM2.5 > 1000 µg/m³) and **PM2.5 readings that exceed PM10** at the same station
  (physically impossible — PM2.5 is a subset of PM10). Caps are generous so genuine
  extreme-pollution days are retained.
