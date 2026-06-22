// AQI standard metadata for the UI: category bands, colour-blind-safe colours, and
// category lookup. Mirrors the pipeline engine's categories; the pipeline precomputes the
// numbers, this maps them to labels + colours for display. Colour is ALWAYS paired with the
// label in the UI - never colour alone.

export type StandardId = "naqi" | "us" | "eu";

export interface Band {
  label: string;
  color: string;
  max?: number; // upper index bound (numeric standards only)
}

// Colour-blind-safe AQI palette (paired with text labels everywhere).
const C = {
  good: "#2E9E6B",
  satisfactory: "#8FBF3F",
  moderate: "#E0A100",
  poor: "#D86A2E",
  veryPoor: "#C8455B",
  severe: "#8C2D2D",
};

export const STANDARDS: Record<
  StandardId,
  { name: string; numeric: boolean; max: number; bands: Band[] }
> = {
  naqi: {
    name: "India NAQI",
    numeric: true,
    max: 500,
    bands: [
      { label: "Good", color: C.good, max: 50 },
      { label: "Satisfactory", color: C.satisfactory, max: 100 },
      { label: "Moderate", color: C.moderate, max: 200 },
      { label: "Poor", color: C.poor, max: 300 },
      { label: "Very Poor", color: C.veryPoor, max: 400 },
      { label: "Severe", color: C.severe, max: 500 },
    ],
  },
  us: {
    name: "US EPA AQI",
    numeric: true,
    max: 500,
    bands: [
      { label: "Good", color: C.good, max: 50 },
      { label: "Moderate", color: C.satisfactory, max: 100 },
      { label: "Unhealthy for Sensitive Groups", color: C.moderate, max: 150 },
      { label: "Unhealthy", color: C.poor, max: 200 },
      { label: "Very Unhealthy", color: C.veryPoor, max: 300 },
      { label: "Hazardous", color: C.severe, max: 500 },
    ],
  },
  eu: {
    name: "EU EAQI",
    numeric: false,
    max: 0,
    bands: [
      { label: "Good", color: C.good },
      { label: "Fair", color: C.satisfactory },
      { label: "Moderate", color: C.moderate },
      { label: "Poor", color: C.poor },
      { label: "Very Poor", color: C.veryPoor },
      { label: "Extremely Poor", color: C.severe },
    ],
  },
};

export function bandForIndex(standard: StandardId, index: number): Band {
  const bands = STANDARDS[standard].bands;
  for (const b of bands) if (b.max !== undefined && index <= b.max) return b;
  return bands[bands.length - 1];
}

const UNKNOWN_BAND: Band = { label: "Unknown", color: "#9095a0" };

export function bandByLabel(standard: StandardId, label: string | null): Band {
  // Fall back to neutral grey (not "Good"/green) so an unexpected label never miscolours a
  // hazardous reading as safe.
  return STANDARDS[standard].bands.find((b) => b.label === label) ?? UNKNOWN_BAND;
}

export const POLLUTANT_LABELS: Record<string, string> = {
  pm25: "PM2.5",
  pm10: "PM10",
  no2: "NO₂",
  so2: "SO₂",
  o3: "O₃",
  co: "CO",
  nh3: "NH₃",
};
