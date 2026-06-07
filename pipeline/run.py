"""Orchestrates a full, idempotent data refresh.

Phase 5+. Pipeline: fetch (ingest/*) -> compute AQI (aqi/*) -> aggregate & reconcile
(transform/*) -> write data/live (JSON), data/history + data/recent (Parquet), and
data/meta (city list, station map, coverage report).

Re-running reproduces the same outputs; gaps backfill on the next run.

Usage (later phases):
    python run.py --mode hourly   # CPCB live + Open-Meteo current
    python run.py --mode daily    # OpenAQ + Open-Meteo archive deltas, rebuild
"""


def main() -> None:
    raise SystemExit("Pipeline orchestration is implemented in a later phase.")


if __name__ == "__main__":
    main()
