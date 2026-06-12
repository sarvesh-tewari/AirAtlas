import { useMemo } from "react";
import { Sigma } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import { STANDARDS, bandForIndex, type StandardId } from "../lib/standards";
import type { DailyRow } from "../lib/data";

export function YearSummary({ rows, standard }: { rows: DailyRow[]; standard: StandardId }) {
  const cfg = STANDARDS[standard];

  const years = useMemo(() => {
    const by = new Map<string, number[]>();
    for (const r of rows) {
      const v = cfg.numeric ? (standard === "naqi" ? r.aqi_naqi : r.aqi_us)
        : (r.eu_band ? cfg.bands.findIndex((b) => b.label === r.eu_band) : null);
      if (v == null) continue;
      const yr = r.date.slice(0, 4);
      (by.get(yr) ?? by.set(yr, []).get(yr)!).push(v);
    }
    const poorCut = cfg.numeric ? (standard === "naqi" ? 200 : 150) : 3; // Poor+ band index 3
    return [...by.entries()].sort().map(([yr, vs]) => {
      const avg = Math.round(vs.reduce((a, b) => a + b, 0) / vs.length);
      const peak = Math.max(...vs);
      const good = vs.filter((v) => (cfg.numeric ? v <= 50 : v <= 1)).length;
      const poor = vs.filter((v) => v > poorCut || (!cfg.numeric && v >= poorCut)).length;
      return { yr, avg, peak, good, poor, n: vs.length };
    });
  }, [rows, standard, cfg]);

  if (years.length === 0) return null;
  const fmt = (v: number) => (cfg.numeric ? `${v}` : cfg.bands[Math.min(5, v)]?.label ?? `${v}`);

  return (
    <section className="card p-5">
      <div className="mb-3"><SectionTitle icon={Sigma} color="#0d9488">Year-by-year</SectionTitle></div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {years.map((y) => {
          const peakColor = cfg.numeric ? bandForIndex(standard, y.peak).color : cfg.bands[Math.min(5, y.peak)].color;
          return (
            <div key={y.yr} className="rounded-lg border border-border bg-surface-2/40 p-3">
              <div className="font-display text-lg text-ink">{y.yr}</div>
              <div className="mt-1 flex items-baseline justify-between text-sm">
                <span className="text-muted">avg</span><span className="font-medium text-ink">{fmt(y.avg)}</span>
              </div>
              <div className="flex items-baseline justify-between text-sm">
                <span className="text-muted">peak</span><span className="font-medium" style={{ color: peakColor }}>{fmt(y.peak)}</span>
              </div>
              <div className="mt-1 flex justify-between text-xs text-faint">
                <span>{y.good} good</span><span>{y.poor} poor</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
