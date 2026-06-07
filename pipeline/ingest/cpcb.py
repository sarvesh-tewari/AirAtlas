"""CPCB live fetch via data.gov.in ("Real time Air Quality Index from various locations").

Phase 3. Reads DATA_GOV_IN_KEY from the environment. Returns today's per-station raw
pollutant concentrations. Keeps the last good snapshot on failure (no overwrite with empty).
"""
