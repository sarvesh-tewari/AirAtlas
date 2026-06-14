// Data-access layer: loads the published meta, live JSON, and per-city daily Parquet
// (the last via DuckDB-WASM). All paths are relative to the deploy base.

import { queryParquet } from "./duckdb";

const BASE = `${import.meta.env.BASE_URL}data`;

// Cache-buster: data files live at stable URLs but their CONTENT changes on every refresh, so
// without a version query the CDN/browser serves stale data after a publish. VITE_DATA_VERSION is
// set at deploy time to the data-branch commit SHA, so it changes exactly when the data does:
// files stay cacheable within a deploy and bust the moment new data is published.
const DATA_VERSION = (import.meta.env as Record<string, string | undefined>).VITE_DATA_VERSION ?? "";
const V = DATA_VERSION ? `?v=${DATA_VERSION}` : "";

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
  nh3: number | null;
  aqi_naqi: number | null;
  naqi_category: string | null;
  naqi_dominant: string | null;
  aqi_us: number | null;
  us_category: string | null;
  us_dominant: string | null;
  eu_band: string | null;
  eu_dominant: string | null;
  temp_c: number | null;
  rh_pct: number | null;
  precip_mm: number | null;
  wind_ms: number | null;
}

export interface CityIndex {
  city: string;
  lat: number | null;
  lon: number | null;
  last_date: string;
  n_stations: number;
  naqi: number | null;
  naqi_category: string | null;
  us: number | null;
  us_category: string | null;
  eu_band: string | null;
}

// Safe JSON GET: returns null on 404 or when the server returns HTML (dev SPA fallback).
async function getJSON<T>(url: string): Promise<T | null> {
  const r = await fetch(url);
  if (!r.ok) return null;
  if (!(r.headers.get("content-type") ?? "").includes("json")) return null;
  try {
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export async function fetchCityList(): Promise<CityList> {
  return (await getJSON<CityList>(`${BASE}/meta/city_list.json${V}`)) ?? { generated_today: "", cities: [] };
}

// Rich per-city index (centroid + latest AQI). Falls back to names-only if absent.
export async function fetchCities(): Promise<CityIndex[]> {
  const rich = await getJSON<CityIndex[]>(`${BASE}/meta/cities.json${V}`);
  if (Array.isArray(rich) && rich.length) return rich;
  const list = await fetchCityList();
  return list.cities.map((city) => ({
    city, lat: null, lon: null, last_date: "", n_stations: 0,
    naqi: null, naqi_category: null, us: null, us_category: null, eu_band: null,
  }));
}

export async function fetchLive(city: string): Promise<LiveSnapshot | null> {
  return getJSON<LiveSnapshot>(`${BASE}/live/${slug(city)}.json${V}`);
}

export async function fetchDailyHistory(city: string): Promise<DailyRow[]> {
  const url = `${new URL(BASE, window.location.href).href}/history/${slug(city)}.parquet${V}`;
  return queryParquet<DailyRow>(url, (t) => `SELECT * FROM ${t} ORDER BY date`);
}
