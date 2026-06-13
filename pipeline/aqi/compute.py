"""AQI computation: piecewise-linear sub-index, overall index, unit conversion.

Principle: AQI is a *formula, not a measurement*. We store raw concentrations and
compute any standard on demand. Each standard:
  (a) per-pollutant sub-index from its breakpoint table (piecewise linear), then
  (b) overall = max sub-index (NAQI/US) or worst band (EU).

Sub-index formula:
    I = (I_hi − I_lo) / (BP_hi − BP_lo) × (C − BP_lo) + I_lo
with C truncated to the standard's stated precision before lookup.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import breakpoints as bp


# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #
@dataclass
class AQIResult:
    standard: str                              # "naqi" | "us" | "eu"
    index: int | None = None                   # 0–500 number (None for EU)
    band: str | None = None                    # EU band name (None for NAQI/US)
    category: str | None = None                # human label
    dominant: list[str] = field(default_factory=list)  # pollutant(s) driving it
    subindices: dict[str, int] = field(default_factory=dict)  # NAQI/US per-pollutant
    bands: dict[str, str] = field(default_factory=dict)       # EU per-pollutant band
    valid: bool = True
    off_scale: bool = False


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _truncate(value: float, decimals: int) -> float:
    """Truncate (not round) toward zero to `decimals` places, per AQI convention."""
    factor = 10 ** decimals
    return math.floor(value * factor) / factor


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def ugm3_to_ppb(pollutant: str, value_ugm3: float) -> float:
    """Convert µg/m³ -> ppb at 25 °C, 1 atm (EPA reference conditions)."""
    mw = bp.MOLECULAR_WEIGHT[pollutant]
    return value_ugm3 * bp.MOLAR_VOLUME_25C / mw


def ugm3_to_ppm(pollutant: str, value_ugm3: float) -> float:
    return ugm3_to_ppb(pollutant, value_ugm3) / 1000.0


def _to_native_us(pollutant: str, value: float) -> float:
    """Convert a stored concentration to the US table's native unit for `pollutant`.

    PM2.5/PM10 stay µg/m³; NO2/SO2 -> ppb; O3 -> ppm (from µg/m³); CO -> ppm (from mg/m³).
    """
    if pollutant in ("pm25", "pm10"):
        return value
    if pollutant in ("no2", "so2"):
        return ugm3_to_ppb(pollutant, value)
    if pollutant == "o3":
        return ugm3_to_ppm(pollutant, value)
    if pollutant == "co":
        # CO is stored in mg/m³; ppm = mg/m³ × molar_volume / MW.
        return value * bp.MOLAR_VOLUME_25C / bp.MOLECULAR_WEIGHT["co"]
    raise ValueError(f"Unknown US pollutant: {pollutant}")


def _interp(conc: float, segments: list[tuple[float, float, int, int]],
            off_scale: int = 500) -> tuple[int, bool]:
    """Piecewise-linear sub-index. Returns (value, off_scale_flag).

    Below the first segment -> 0. Above the last closed segment -> `off_scale` (the index
    cap for that pollutant), flagged off_scale.
    """
    if conc <= segments[0][0]:
        return 0, False
    for c_lo, c_hi, i_lo, i_hi in segments:
        if c_lo <= conc <= c_hi:
            value = (i_hi - i_lo) / (c_hi - c_lo) * (conc - c_lo) + i_lo
            return _round_half_up(value), False
    return off_scale, True  # above the top closed breakpoint


# --------------------------------------------------------------------------- #
# Per-pollutant sub-index (NAQI / US)
# --------------------------------------------------------------------------- #
def sub_index(standard: str, pollutant: str, concentration: float) -> int:
    """Per-pollutant sub-index for NAQI or US. (EU has no numeric sub-index.)"""
    value, _ = _sub_index_full(standard, pollutant, concentration)
    return value


def _sub_index_full(standard: str, pollutant: str, concentration: float) -> tuple[int, bool]:
    if standard == "naqi":
        prec = bp.NAQI_PRECISION[pollutant]
        c = _truncate(concentration, prec)
        return _interp(c, bp.NAQI[pollutant], off_scale=500)  # NAQI Severe tops at 500
    if standard == "us":
        native = _to_native_us(pollutant, concentration)
        prec = bp.US_PRECISION[pollutant]
        c = _truncate(native, prec)
        # Above a US pollutant's tabulated range, cap at that pollutant's max tabulated index
        # (O3 -> 300, SO2 -> 200; PM/CO/NO2 -> 500) rather than always 500.
        return _interp(c, bp.US[pollutant], off_scale=bp.US[pollutant][-1][3])
    raise ValueError(f"sub_index not defined for standard {standard!r}")


# --------------------------------------------------------------------------- #
# EU banding
# --------------------------------------------------------------------------- #
def eu_band(pollutant: str, concentration: float) -> str:
    thresholds = bp.EU_THRESHOLDS[pollutant]
    for i, upper in enumerate(thresholds):
        if concentration <= upper:
            return bp.EU_BANDS[i]
    return bp.EU_BANDS[-1]  # above the last threshold -> Extremely Poor


# --------------------------------------------------------------------------- #
# Category lookup (NAQI / US)
# --------------------------------------------------------------------------- #
def _category(standard: str, index: int) -> str:
    table = bp.NAQI_CATEGORIES if standard == "naqi" else bp.US_CATEGORIES
    for lo, hi, name in table:
        if lo <= index <= hi:
            return name
    return table[-1][2]


# --------------------------------------------------------------------------- #
# Overall index
# --------------------------------------------------------------------------- #
def overall(standard: str, concentrations: dict[str, float]) -> AQIResult:
    """Overall AQI for one location from its per-pollutant concentrations."""
    if standard == "eu":
        return _overall_eu(concentrations)
    if standard in ("naqi", "us"):
        return _overall_index(standard, concentrations)
    raise ValueError(f"Unknown standard: {standard!r}")


def _overall_index(standard: str, concentrations: dict[str, float]) -> AQIResult:
    table = bp.NAQI if standard == "naqi" else bp.US
    subs: dict[str, int] = {}
    off = False
    for pollutant, conc in concentrations.items():
        if pollutant not in table or conc is None:
            continue
        value, seg_off = _sub_index_full(standard, pollutant, conc)
        subs[pollutant] = value
        off = off or seg_off

    result = AQIResult(standard=standard, subindices=subs, off_scale=off)

    if standard == "naqi" and not _naqi_valid(subs):
        result.valid = False
        return result
    if not subs:
        result.valid = False
        return result

    top = max(subs.values())
    result.index = top
    result.category = _category(standard, top)
    result.dominant = [p for p, v in subs.items() if v == top]
    return result


def _naqi_valid(subs: dict[str, int]) -> bool:
    """NAQI requires >=3 pollutants present, one of which is PM2.5 or PM10."""
    return len(subs) >= 3 and ({"pm25", "pm10"} & subs.keys() != set())


def _overall_eu(concentrations: dict[str, float]) -> AQIResult:
    bands: dict[str, str] = {}
    for pollutant, conc in concentrations.items():
        if pollutant not in bp.EU_THRESHOLDS or conc is None:
            continue
        bands[pollutant] = eu_band(pollutant, conc)

    result = AQIResult(standard="eu", bands=bands)
    if not bands:
        result.valid = False
        return result

    worst_rank = max(bp.EU_BANDS.index(b) for b in bands.values())
    worst = bp.EU_BANDS[worst_rank]
    result.band = worst
    result.category = worst
    result.dominant = [p for p, b in bands.items() if b == worst]
    return result


# --------------------------------------------------------------------------- #
# NAQI city aggregation
# --------------------------------------------------------------------------- #
def city_index_naqi(stations: list[dict[str, float]]) -> AQIResult:
    """City NAQI: require >=3 stations; average each pollutant's sub-index across
    stations, THEN take the max across pollutants (note: average, not max, across
    stations — per CPCB)."""
    if len(stations) < 3:
        return AQIResult(standard="naqi", valid=False)

    # Collect per-pollutant sub-index lists across stations.
    per_pollutant: dict[str, list[int]] = {}
    off = False
    for station in stations:
        for pollutant, conc in station.items():
            if pollutant not in bp.NAQI or conc is None:
                continue
            value, seg_off = _sub_index_full("naqi", pollutant, conc)
            per_pollutant.setdefault(pollutant, []).append(value)
            off = off or seg_off

    # Average each pollutant's sub-index across the stations that reported it.
    avg_subs = {p: _round_half_up(sum(v) / len(v)) for p, v in per_pollutant.items()}

    result = AQIResult(standard="naqi", subindices=avg_subs, off_scale=off)
    if not _naqi_valid(avg_subs):
        result.valid = False
        return result

    top = max(avg_subs.values())
    result.index = top
    result.category = _category("naqi", top)
    result.dominant = [p for p, v in avg_subs.items() if v == top]
    return result
