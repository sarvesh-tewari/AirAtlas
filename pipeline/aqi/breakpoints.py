"""Breakpoint tables for the three AQI standards.

Phase 2 will encode:
  - India NAQI (CPCB 2014): 8 pollutants, µg/m³ (CO in mg/m³).
  - US EPA AQI (eff. 2024-05-06): 6 pollutants, gases in ppb/ppm, PM in µg/m³.
  - EU EAQI (EEA 2024 revision): 5 pollutants, 6-band, µg/m³ hourly.

Pin the exact source versions in SOURCES.md. Do not transcribe US gas tables or EU
bands from memory — encode from the cited authoritative sources at implementation time.
"""
