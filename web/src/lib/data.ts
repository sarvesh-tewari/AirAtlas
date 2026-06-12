// Data-access layer: loads the published meta, live JSON, and per-city daily Parquet
// (the last via DuckDB-WASM). All paths are relative to the deploy base.

import { queryParquet } from "./duckdb";

const BASE = `${import.meta.env.BASE_URL}data`;

export function slug(city: string): string {
  return city.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export interface CityList {
  generated_today: string;
  cities: string[];
}

export interface AqiResult {
  index: number | null;
  band: string | null;
  category: string | null;
  dominant: string[];
  valid: boolean;
}

export interface LiveSnapshot {
  city: string;
  updated_utc: string;
  source: string | null;
  n_stations: number;
  pollutants: Record<string, { value: number; unit: string; naqi_subindex: number; us_subindex: number }>;
  aqi: { naqi: AqiResult; us: AqiResult; eu: AqiResult };
  weather: { temp_c?: number; rh_pct?: number; precip_mm?: number; wind_ms?: number; wind_dir_deg?: number } | null;
}

export interface DailyRow {
  city: string;
  date: string;
  source: string;
  n_stations: number;
  pm25: number | null;
  pm10: number | null;
  no2: number | null;
  so2: number | null;
  o3: number | null;
  co: number | null;
  aqi_naqi: number | null;
  naqi_category: string | null;
  aqi_us: number | null;
  us_category: string | null;
  eu_band: string | null;
  temp_c: number | null;
  rh_pct: number | null;
  precip_mm: number | null;
  wind_ms: number | null;
}

export async function fetchCityList(): Promise<CityList> {
  const r = await fetch(`${BASE}/meta/city_list.json`);
  if (!r.ok) throw new Error(`city_list.json ${r.status}`);
  return r.json();
}

export async function fetchLive(city: string): Promise<LiveSnapshot | null> {
  const r = await fetch(`${BASE}/live/${slug(city)}.json`);
  return r.ok ? r.json() : null;
}

export async function fetchDailyHistory(city: string): Promise<DailyRow[]> {
  const url = `${new URL(BASE, window.location.href).href}/history/${slug(city)}.parquet`;
  return queryParquet<DailyRow>(url, (t) => `SELECT * FROM ${t} ORDER BY date`);
}
