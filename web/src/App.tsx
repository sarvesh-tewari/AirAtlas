import { useEffect, useMemo, useRef, useState } from "react";
import { TopBar } from "./components/TopBar";
import { Headline, type HeadlineVM } from "./components/Headline";
import { PollutantCards, type PollutantVM } from "./components/PollutantCards";
import { WeatherStrip, type WeatherVM } from "./components/WeatherStrip";
import { TrendChart } from "./components/TrendChart";
import { PollutantTrend } from "./components/PollutantTrend";
import { Exceedance } from "./components/Exceedance";
import { WeatherOverlay } from "./components/WeatherOverlay";
import { Compare } from "./components/Compare";
import { MonthlyHeatmap } from "./components/MonthlyHeatmap";
import { YearSummary } from "./components/YearSummary";
import { MapView } from "./components/MapView";
import { Methodology } from "./components/Methodology";
import { ErrorBoundary } from "./components/ErrorBoundary";
import type { Option } from "./components/Combobox";
import { POLLUTANT_LABELS, type StandardId } from "./lib/standards";
import {
  fetchCities, fetchLive, fetchDailyHistory,
  type CityIndex, type LiveSnapshot, type DailyRow,
} from "./lib/data";

const POLLS = ["pm25", "pm10", "no2", "so2", "o3", "co", "nh3"] as const;

function useTheme() {
  const [dark, setDark] = useState(
    () => localStorage.getItem("theme") === "dark" ||
      (!localStorage.getItem("theme") && matchMedia("(prefers-color-scheme: dark)").matches),
  );
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  return { dark, toggle: () => setDark((d) => !d) };
}

function timeAgo(iso: string): string {
  const h = (Date.now() - new Date(iso).getTime()) / 3.6e6;
  if (h < 1) return `${Math.round(h * 60)}m ago`;
  if (h < 48) return `${Math.round(h)}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

function nearestCity(cities: CityIndex[], lat: number, lon: number): string | null {
  let best: string | null = null, bestD = Infinity;
  for (const c of cities) {
    if (c.lat == null || c.lon == null) continue;
    const d = (c.lat - lat) ** 2 + (c.lon - lon) ** 2;
    if (d < bestD) { bestD = d; best = c.city; }
  }
  return best;
}

export default function App() {
  const { dark, toggle } = useTheme();
  const [page, setPage] = useState<"dashboard" | "methodology">("dashboard");
  const [cities, setCities] = useState<CityIndex[]>([]);
  const [city, setCity] = useState("Delhi");
  const [standard, setStandard] = useState<StandardId>("naqi");
  const [live, setLive] = useState<LiveSnapshot | null>(null);
  const [history, setHistory] = useState<DailyRow[]>([]);
  const [histLoading, setHistLoading] = useState(true);
  const pickedRef = useRef(false); // user manually chose a city (read inside async callbacks)
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchCities()
      .then((cs) => {
        setCities(cs);
        if (cs.length && !cs.some((c) => c.city === city)) setCity(cs[0].city);
        if (!pickedRef.current && navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const n = nearestCity(cs, pos.coords.latitude, pos.coords.longitude);
              if (n && !pickedRef.current) setCity(n); // don't override a manual pick made meanwhile
            },
            () => {},
            { timeout: 5000 },
          );
        }
      })
      .catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load the selected city; guard against out-of-order resolution (fast city toggling).
  useEffect(() => {
    if (!city) return;
    let alive = true;
    setLive(null);
    setHistory([]);
    setHistLoading(true);
    fetchLive(city).then((v) => alive && setLive(v)).catch(() => alive && setLive(null));
    fetchDailyHistory(city)
      .then((r) => { if (alive) setHistory(r); })
      .catch((e) => alive && setErr(String(e)))
      .finally(() => { if (alive) setHistLoading(false); });
    return () => { alive = false; };
  }, [city]);

  const lastRow = history.length ? history[history.length - 1] : null;

  const headline: HeadlineVM = useMemo(() => {
    const base: HeadlineVM = {
      city, index: null, band: null, category: null, dominantLabel: null,
      dominantValue: null, dominantUnit: null, stale: !live, live: !!live,
      nStations: live?.n_stations ?? lastRow?.n_stations ?? 0,
    };
    let dominant: string[] = [];
    if (live) {
      if (standard === "eu") { base.band = live.aqi.eu.band; base.category = live.aqi.eu.category; }
      else { base.index = live.aqi[standard].index; base.category = live.aqi[standard].category; }
      dominant = live.aqi[standard].dominant;
      base.stale = (Date.now() - new Date(live.updated_utc).getTime()) / 3.6e6 > 6;
    } else {
      const split = (s: string | null) => (s ? s.split(",") : []);
      for (let i = history.length - 1; i >= 0; i--) {
        const r = history[i];
        if (standard === "eu") {
          if (r.eu_band) { base.band = r.eu_band; base.category = r.eu_band; dominant = split(r.eu_dominant); break; }
          continue;
        }
        const idx = standard === "naqi" ? r.aqi_naqi : r.aqi_us;
        if (idx != null) {
          base.index = idx;
          base.category = standard === "naqi" ? r.naqi_category : r.us_category;
          dominant = split(standard === "naqi" ? r.naqi_dominant : r.us_dominant);
          break;
        }
      }
    }
    const domKey = dominant[0];
    if (domKey) {
      base.dominantLabel = POLLUTANT_LABELS[domKey] ?? domKey;
      const v = live ? live.pollutants[domKey]?.value : (lastRow?.[domKey as keyof DailyRow] as number | null);
      base.dominantValue = v ?? null;
      base.dominantUnit = domKey === "co" ? "mg/m³" : "µg/m³";
    }
    return base;
  }, [live, history, standard, city, lastRow]);

  const pollutants: PollutantVM[] = useMemo(() => {
    if (live) {
      const dom = new Set(live.aqi[standard].dominant);
      return Object.entries(live.pollutants).map(([k, v]) => ({
        key: k, value: v.value, unit: v.unit,
        subindex: standard === "naqi" ? v.naqi_subindex : standard === "us" ? v.us_subindex : null,
        dominant: dom.has(k),
      }));
    }
    if (lastRow) {
      const domStr = standard === "naqi" ? lastRow.naqi_dominant : standard === "us" ? lastRow.us_dominant : lastRow.eu_dominant;
      const dom = new Set((domStr ?? "").split(",").filter(Boolean));
      return POLLS.filter((k) => lastRow[k] != null).map((k) => ({
        key: k, value: lastRow[k] as number, unit: k === "co" ? "mg/m³" : "µg/m³",
        subindex: null, dominant: dom.has(k),
      }));
    }
    return [];
  }, [live, lastRow, standard]);

  const weather: WeatherVM | null = useMemo(() => {
    if (live?.weather) return { temp_c: live.weather.temp_c ?? null, rh_pct: live.weather.rh_pct ?? null, precip_mm: live.weather.precip_mm ?? null, wind_ms: live.weather.wind_ms ?? null };
    if (lastRow) return { temp_c: lastRow.temp_c, rh_pct: lastRow.rh_pct, precip_mm: lastRow.precip_mm, wind_ms: lastRow.wind_ms };
    return null;
  }, [live, lastRow]);

  const cityOptions: Option[] = useMemo(
    () => cities.map((c) => ({ value: c.city, label: c.city, hint: c.naqi != null ? `${c.naqi}` : undefined })),
    [cities],
  );

  const updatedLabel = live ? timeAgo(live.updated_utc) : lastRow ? `as of ${lastRow.date}` : null;
  const source = live?.source ?? lastRow?.source ?? null;

  const cityNames = useMemo(() => cities.map((c) => c.city), [cities]);

  function chooseCity(c: string) { pickedRef.current = true; setCity(c); }

  return (
    <div className="min-h-full">
      <a href="#main" className="skip-link">Skip to content</a>
      <TopBar
        cities={cityOptions} city={city} onCity={chooseCity}
        standard={standard} onStandard={setStandard}
        updatedLabel={updatedLabel} source={source}
        dark={dark} onToggleTheme={toggle} page={page} onNav={setPage}
      />

      <main id="main" className="mx-auto max-w-6xl px-5 py-6">
        {err && <p className="mb-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">{err}</p>}

        {page === "methodology" ? (
          <Methodology />
        ) : (
          <div className="flex flex-col gap-6">
            <ErrorBoundary label="Headline"><Headline standard={standard} vm={headline} loading={histLoading && !live} /></ErrorBoundary>
            {cities.some((c) => c.lat != null) && (
              <ErrorBoundary label="Map">
                <MapView cities={cities} standard={standard} current={city} onCity={chooseCity} dark={dark} />
              </ErrorBoundary>
            )}
            <WeatherStrip vm={weather} />
            <PollutantCards pollutants={pollutants} />
            {history.length > 1 && (
              <>
                <ErrorBoundary label="Trend"><TrendChart rows={history} standard={standard} dark={dark} /></ErrorBoundary>
                <ErrorBoundary label="Monthly pattern"><MonthlyHeatmap rows={history} standard={standard} dark={dark} /></ErrorBoundary>
                <ErrorBoundary label="Year-by-year"><YearSummary rows={history} standard={standard} /></ErrorBoundary>
                <ErrorBoundary label="Pollutant trends"><PollutantTrend rows={history} dark={dark} /></ErrorBoundary>
                <ErrorBoundary label="Exceedance"><Exceedance rows={history} standard={standard} dark={dark} /></ErrorBoundary>
                <ErrorBoundary label="Weather overlay"><WeatherOverlay rows={history} standard={standard} dark={dark} /></ErrorBoundary>
                <ErrorBoundary label="Compare"><Compare available={cityNames} current={city} standard={standard} dark={dark} /></ErrorBoundary>
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
