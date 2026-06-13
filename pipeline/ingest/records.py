"""Normalized ingestion schema + unit helpers.

All three sources (CPCB, OpenAQ, Open-Meteo) are parsed into these common records so
the transform/AQI layers don't care where data came from. Concentrations are normalized
to the engine's expected units: **µg/m³ for everything except CO, which is mg/m³**.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aqi import breakpoints as bp

# --------------------------------------------------------------------------- #
# Canonical pollutant keys we track: pm25, pm10, no2, so2, o3, co, nh3
# --------------------------------------------------------------------------- #
_POLLUTANT_CANON = {
    "pm2.5": "pm25", "pm25": "pm25",
    "pm10": "pm10",
    "no2": "no2",
    "so2": "so2",
    "o3": "o3", "ozone": "o3",
    "co": "co",
    "nh3": "nh3",
}


def canonical_pollutant(name: str) -> str | None:
    """Map a source pollutant label to our canonical key, or None if untracked."""
    if name is None:
        return None
    return _POLLUTANT_CANON.get(str(name).strip().lower())


def canonical_unit(pollutant: str) -> str:
    return "mg/m³" if pollutant == "co" else "µg/m³"


def ppb_to_ugm3(pollutant: str, ppb: float) -> float:
    """ppb -> µg/m³ at 25 °C, 1 atm (inverse of the engine's µg/m³ -> ppb)."""
    return ppb * bp.MOLECULAR_WEIGHT[pollutant] / bp.MOLAR_VOLUME_25C


def normalize_concentration(pollutant: str, value: float, unit: str | None) -> tuple[float, str]:
    """Return (value_in_canonical_unit, canonical_unit) for a pollutant.

    Handles ppb/ppm -> µg/m³ (and -> mg/m³ for CO). µg/m³ / mg/m³ pass through.
    """
    u = (unit or "").strip().lower().replace("μ", "µ")
    target = canonical_unit(pollutant)

    if pollutant == "co":
        # CPCB reports CO in mg/m³. OpenAQ frequently mislabels these as "ppb" while the
        # value is really mg/m³ (~0–50). Disambiguate by magnitude: a genuine CO ppb reading
        # is in the hundreds–thousands. (1 ppm CO ≈ 1.145 mg/m³.)
        if "ppm" in u:
            return value * 1.145, "mg/m³"
        if "ppb" in u:
            return (ppb_to_ugm3("co", value) / 1000.0, "mg/m³") if value > 60 else (value, "mg/m³")
        if "µg" in u or "ug" in u:
            return value / 1000.0, "mg/m³"  # µg/m³ -> mg/m³
        return value, "mg/m³"  # already mg/m³ (or unlabeled)

    if "ppm" in u:
        value = value * 1000.0  # ppm -> ppb
        u = "ppb"
    if "ppb" in u:
        ug = ppb_to_ugm3(pollutant, value)
        return (ug / 1000.0, "mg/m³") if pollutant == "co" else (ug, "µg/m³")

    # Already mass-per-volume. Trust the canonical unit for the pollutant.
    return value, target


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Sensor:
    sensor_id: int
    parameter: str       # canonical
    units: str           # source units (e.g. "µg/m³", "ppb")


@dataclass
class Station:
    source: str
    station_id: str
    name: str
    lat: float | None = None
    lon: float | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    timezone: str | None = None
    sensors: list[Sensor] = field(default_factory=list)


@dataclass
class AQRecord:
    source: str                 # "cpcb" | "openaq"
    station_id: str
    station_name: str | None
    city: str | None
    state: str | None
    lat: float | None
    lon: float | None
    parameter: str              # canonical
    value: float | None         # canonical unit (µg/m³, CO mg/m³)
    unit: str
    datetime_utc: str           # ISO 8601, trailing Z
    averaging: str              # "live" | "1h" | "1d"
    coverage_pct: float | None = None


@dataclass
class WeatherRecord:
    source: str                 # "open-meteo"
    lat: float
    lon: float
    datetime_utc: str
    averaging: str              # "live" | "1h" | "1d"
    temp_c: float | None = None
    rh_pct: float | None = None
    precip_mm: float | None = None
    wind_speed_ms: float | None = None
    wind_dir_deg: float | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
