"""AQI computation: piecewise-linear sub-index, overall index, unit conversion.

Phase 2 will implement:
  - sub_index(concentration, pollutant, standard) via the piecewise-linear formula
        I = (I_hi - I_lo) / (BP_hi - BP_lo) * (C - BP_lo) + I_lo
    with C truncated to each standard's stated precision before lookup.
  - overall index per standard's rule (max sub-index; EU = worst band).
  - µg/m³ -> ppb conversion for US gaseous pollutants.
  - city aggregation rules (e.g. NAQI: >=3 stations, average sub-index per pollutant
    across stations, then max across pollutants).
"""
