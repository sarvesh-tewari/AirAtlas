"""Aggregation: station -> city and hourly -> daily.

Phase 4. Applies the NAQI city rule (>=3 stations; average each pollutant's sub-index
across stations, then max across pollutants) and derives each standard's required
averaging window from stored hourly raw data.
"""
