"""Tests for the AQI engine — implemented in Phase 2.

Locks the §7 regression case (same 24h concentrations, three standards):
  Input: PM2.5=90, PM10=250, NO2=80, SO2=40 µg/m³
    India NAQI -> 200  "Moderate"      (dominant PM2.5/PM10)
    US EPA AQI -> ~175 "Unhealthy"     (dominant PM2.5)
    EU EAQI    -> "Extremely Poor"     (dominant PM2.5/PM10)

Placeholder until the engine lands; keeps the test module discoverable.
"""

import pytest


@pytest.mark.skip(reason="AQI engine implemented in Phase 2")
def test_regression_three_standards_same_air():
    raise NotImplementedError
