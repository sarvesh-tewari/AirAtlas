"""Breakpoint tables for the three AQI standards.

Sources (pinned in SOURCES.md):
  - India NAQI: CPCB 2014 National Air Quality Index.
  - US EPA AQI: EPA AQS code table, effective 2024-05-06 (PM2.5 May 2024 revision).
  - EU EAQI:   EEA 2024-revised bands (ETC HE Report 2024-17), aligned to WHO 2021.

Each NAQI/US segment is (conc_low, conc_high, index_low, index_high) in the unit noted.
NAQI/US overall index = max sub-index across pollutants.
EU is a 6-band category (no 0–500 number); overall = worst band.

Top-of-scale: CPCB leaves the 401–500 band open-topped, so segments are encoded with
closed bounds through the 301–400 band; concentrations above the top closed breakpoint
return AQI 500 flagged off_scale (the whole 401–500 range is one category, "Severe").
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Pollutant canonical keys: pm25, pm10, no2, so2, o3, co, nh3, pb
# Stored concentration units: µg/m³ for everything EXCEPT CO, which is mg/m³.
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# India NAQI (CPCB 2014). Concentrations: µg/m³ (CO in mg/m³).
# Averaging: PM/NO2/SO2/NH3/Pb = 24h; O3/CO = 8h.
# Segments cover Good(0–50) … Very Poor(301–400) with closed bounds.
# --------------------------------------------------------------------------- #
NAQI: dict[str, list[tuple[float, float, int, int]]] = {
    "pm10": [(0, 50, 0, 50), (51, 100, 51, 100), (101, 250, 101, 200),
             (251, 350, 201, 300), (351, 430, 301, 400)],
    "pm25": [(0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200),
             (91, 120, 201, 300), (121, 250, 301, 400)],
    "no2":  [(0, 40, 0, 50), (41, 80, 51, 100), (81, 180, 101, 200),
             (181, 280, 201, 300), (281, 400, 301, 400)],
    "so2":  [(0, 40, 0, 50), (41, 80, 51, 100), (81, 380, 101, 200),
             (381, 800, 201, 300), (801, 1600, 301, 400)],
    "o3":   [(0, 50, 0, 50), (51, 100, 51, 100), (101, 168, 101, 200),
             (169, 208, 201, 300), (209, 748, 301, 400)],
    "co":   [(0, 1.0, 0, 50), (1.1, 2.0, 51, 100), (2.1, 10, 101, 200),
             (10.1, 17, 201, 300), (17.1, 34, 301, 400)],  # mg/m³
    "nh3":  [(0, 200, 0, 50), (201, 400, 51, 100), (401, 800, 101, 200),
             (801, 1200, 201, 300), (1201, 1800, 301, 400)],
    "pb":   [(0, 0.5, 0, 50), (0.6, 1.0, 51, 100), (1.1, 2.0, 101, 200),
             (2.1, 3.0, 201, 300), (3.1, 3.5, 301, 400)],
}

NAQI_CATEGORIES = [
    (0, 50, "Good"), (51, 100, "Satisfactory"), (101, 200, "Moderate"),
    (201, 300, "Poor"), (301, 400, "Very Poor"), (401, 500, "Severe"),
]

# NAQI truncation precision (decimals) per pollutant before lookup.
NAQI_PRECISION = {"pm10": 0, "pm25": 0, "no2": 0, "so2": 0, "o3": 0,
                  "co": 1, "nh3": 0, "pb": 1}

# --------------------------------------------------------------------------- #
# US EPA AQI (effective 2024-05-06). Segments in each pollutant's NATIVE unit:
#   PM2.5, PM10 -> µg/m³ ; O3, CO -> ppm ; NO2, SO2 -> ppb.
# Gases are converted from µg/m³ before lookup (see compute.ugm3_to_*).
# O3 is the 8-hour table (tops at AQI 300), SO2 the 1-hour table (tops at AQI 200). EPA's
# full method switches to 1-hour O3 / 24-hour SO2 above those points; we do NOT encode those
# hybrid curves — a value above the table is capped at that pollutant's max tabulated index
# (see compute._sub_index_full), flagged off_scale, rather than overstating to 500.
# --------------------------------------------------------------------------- #
US: dict[str, list[tuple[float, float, int, int]]] = {
    "pm25": [(0.0, 9.0, 0, 50), (9.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
             (55.5, 125.4, 151, 200), (125.5, 225.4, 201, 300), (225.5, 325.4, 301, 500)],
    "pm10": [(0, 54, 0, 50), (55, 154, 51, 100), (155, 254, 101, 150),
             (255, 354, 151, 200), (355, 424, 201, 300), (425, 604, 301, 500)],
    "o3":   [(0.000, 0.054, 0, 50), (0.055, 0.070, 51, 100), (0.071, 0.085, 101, 150),
             (0.086, 0.105, 151, 200), (0.106, 0.200, 201, 300)],          # ppm, 8-hour
    "co":   [(0.0, 4.4, 0, 50), (4.5, 9.4, 51, 100), (9.5, 12.4, 101, 150),
             (12.5, 15.4, 151, 200), (15.5, 30.4, 201, 300), (30.5, 50.4, 301, 500)],  # ppm
    "so2":  [(0, 35, 0, 50), (36, 75, 51, 100), (76, 185, 101, 150),
             (186, 304, 151, 200)],                                         # ppb, 1-hour
    "no2":  [(0, 53, 0, 50), (54, 100, 51, 100), (101, 360, 101, 150),
             (361, 649, 151, 200), (650, 1249, 201, 300), (1250, 2049, 301, 500)],  # ppb
}

US_CATEGORIES = [
    (0, 50, "Good"), (51, 100, "Moderate"), (101, 150, "Unhealthy for Sensitive Groups"),
    (151, 200, "Unhealthy"), (201, 300, "Very Unhealthy"), (301, 500, "Hazardous"),
]

# US truncation precision (decimals) in the NATIVE unit before lookup.
US_PRECISION = {"pm25": 1, "pm10": 0, "o3": 3, "co": 1, "so2": 0, "no2": 0}

# --------------------------------------------------------------------------- #
# EU EAQI (EEA 2024 revision). Upper-bound-inclusive thresholds, µg/m³.
# Bands: Good, Fair, Moderate, Poor, Very Poor, then Extremely Poor (above last).
# Averaging: PM2.5/PM10 = 24h running mean ; NO2/O3/SO2 = hourly.
# --------------------------------------------------------------------------- #
EU_BANDS = ["Good", "Fair", "Moderate", "Poor", "Very Poor", "Extremely Poor"]

EU_THRESHOLDS: dict[str, list[float]] = {
    "pm25": [5, 15, 50, 90, 140],
    "pm10": [15, 45, 120, 195, 270],
    "no2":  [10, 25, 60, 100, 150],
    "o3":   [60, 100, 120, 160, 180],
    "so2":  [20, 40, 125, 190, 275],
}

# --------------------------------------------------------------------------- #
# µg/m³ <-> ppb conversion (US gases). ppb = C_µg/m³ × MOLAR_VOLUME / MW
# at 25 °C, 1 atm (EPA reference conditions). CO uses mg/m³ -> ppm directly.
# --------------------------------------------------------------------------- #
MOLAR_VOLUME_25C = 24.45            # L/mol at 25 °C, 1013.25 hPa
MOLECULAR_WEIGHT = {                # g/mol
    "no2": 46.0055,
    "so2": 64.066,
    "o3": 48.00,
    "co": 28.010,
}
