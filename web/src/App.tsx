import { useEffect, useMemo, useState } from "react";
import { Gauge } from "./components/Gauge";
import { STANDARDS, bandByLabel, POLLUTANT_LABELS, type StandardId } from "./lib/standards";
import { fetchCityList, fetchLive, fetchDailyHistory, type LiveSnapshot, type DailyRow } from "./lib/data";

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

export default function App() {
  const { dark, toggle } = useTheme();
  const [cities, setCities] = useState<string[]>([]);
  const [city, setCity] = useState<string>("Delhi");
  const [standard, setStandard] = useState<StandardId>("naqi");
  const [live, setLive] = useState<LiveSnapshot | null>(null);
  const [history, setHistory] = useState<DailyRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchCityList()
      .then((cl) => {
        setCities(cl.cities);
        if (cl.cities.length && !cl.cities.includes(city)) setCity(cl.cities[0]);
      })
      .catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!city) return;
    setLive(null);
    setHistory([]);
    fetchLive(city).then(setLive).catch(() => setLive(null));
    fetchDailyHistory(city).then(setHistory).catch((e) => setErr(String(e)));
  }, [city]);

  // Latest known index for the active standard: prefer live, else last history row.
  const headline = useMemo(() => {
    if (live) {
      if (standard === "eu") return { band: live.aqi.eu.band, dominant: live.aqi.eu.dominant, index: null };
      const a = live.aqi[standard];
      return { band: a.category, dominant: a.dominant, index: a.index };
    }
    // Latest row that actually has a value for the active standard.
    for (let i = history.length - 1; i >= 0; i--) {
      const row = history[i];
      if (standard === "eu") {
        if (row.eu_band) return { band: row.eu_band, dominant: [], index: null };
        continue;
      }
      const idx = standard === "naqi" ? row.aqi_naqi : row.aqi_us;
      const cat = standard === "naqi" ? row.naqi_category : row.us_category;
      if (idx != null) return { band: cat, dominant: [], index: idx };
    }
    return null;
  }, [live, history, standard]);

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-black/10 bg-white/80 px-4 py-2.5 backdrop-blur dark:border-white/10 dark:bg-[#16171a]/80">
        <span className="font-medium">🌬 AirAtlas</span>
        <select
          value={city}
          onChange={(e) => setCity(e.target.value)}
          className="rounded-md border border-black/15 bg-transparent px-2 py-1 text-sm dark:border-white/15"
        >
          {(cities.length ? cities : [city]).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <div className="inline-flex overflow-hidden rounded-md border border-black/15 text-xs dark:border-white/15">
          {(["naqi", "us", "eu"] as StandardId[]).map((s) => (
            <button
              key={s}
              onClick={() => setStandard(s)}
              className={`px-2.5 py-1 ${standard === s ? "bg-sky-600 text-white" : "opacity-70"}`}
            >
              {s === "naqi" ? "NAQI" : s === "us" ? "US" : "EU"}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3 text-xs opacity-70">
          {live && <span>updated {timeAgo(live.updated_utc)}</span>}
          <button onClick={toggle} className="rounded-md border border-black/15 px-2 py-1 dark:border-white/15">
            {dark ? "☀ light" : "☾ dark"}
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        {err && <p className="mb-4 rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">{err}</p>}

        <section className="rounded-xl border border-black/10 bg-white p-6 dark:border-white/10 dark:bg-[#1e2024]">
          <p className="mb-1 text-sm opacity-60">{city} · {STANDARDS[standard].name}</p>
          {headline?.index != null ? (
            <div className="flex flex-col items-center">
              <Gauge standard={standard} index={headline.index} />
            </div>
          ) : headline?.band ? (
            <div
              className="my-3 inline-block rounded-md px-4 py-2 font-medium"
              style={{ background: bandByLabel(standard, headline.band).color, color: "#fff" }}
            >
              {headline.band}
            </div>
          ) : (
            <p className="py-8 text-center opacity-60">Loading…</p>
          )}
          {headline?.dominant && headline.dominant.length > 0 && (
            <p className="text-center text-sm opacity-70">
              Dominant: {headline.dominant.map((d) => POLLUTANT_LABELS[d] ?? d).join(", ")}
            </p>
          )}
        </section>

        <section className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {live &&
            Object.entries(live.pollutants).map(([p, v]) => (
              <div key={p} className="rounded-lg border border-black/10 bg-white p-3 dark:border-white/10 dark:bg-[#1e2024]">
                <div className="text-xs opacity-60">{POLLUTANT_LABELS[p] ?? p}</div>
                <div className="text-lg font-medium">{Math.round(v.value * 10) / 10}</div>
                <div className="text-[11px] opacity-50">{v.unit}</div>
              </div>
            ))}
        </section>

        <p className="mt-6 text-xs opacity-50">
          {history.length > 0
            ? `DuckDB-WASM: loaded ${history.length} daily rows for ${city} (${history[0].date} → ${history[history.length - 1].date}).`
            : "DuckDB-WASM: loading history…"}
        </p>
      </main>
    </div>
  );
}
