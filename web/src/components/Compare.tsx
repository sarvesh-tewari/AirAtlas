import { useEffect, useMemo, useState } from "react";
import type { EChartsCoreOption } from "echarts";
import { BarChart3 } from "lucide-react";
import { EChart, chartTheme } from "./EChart";
import { SectionTitle } from "./SectionTitle";
import { STANDARDS, type StandardId } from "../lib/standards";
import { fetchDailyHistory, type DailyRow } from "../lib/data";

const LINE = ["#24426b", "#ef4444", "#10b981", "#f59e0b", "#a855f7", "#0ea5e9"];

export function Compare({ available, current, standard, dark }: { available: string[]; current: string; standard: StandardId; dark: boolean }) {
  const t = chartTheme(dark);
  const cfg = STANDARDS[standard];
  const [selected, setSelected] = useState<string[]>([]);
  const [data, setData] = useState<Record<string, DailyRow[]>>({});

  // Seed with the current city + up to two others.
  useEffect(() => {
    const seed = [current, ...available.filter((c) => c !== current)].slice(0, 3);
    setSelected(seed);
  }, [current, available]);

  useEffect(() => {
    selected.forEach((c) => {
      if (!data[c]) fetchDailyHistory(c).then((rows) => setData((d) => ({ ...d, [c]: rows }))).catch(() => {});
    });
  }, [selected, data]);

  function toggle(c: string) {
    setSelected((s) => (s.includes(c) ? s.filter((x) => x !== c) : s.length < 6 ? [...s, c] : s));
  }

  const aqiKey = standard === "us" ? "aqi_us" : "aqi_naqi";
  const option = useMemo(() => ({
    grid: { left: 44, right: 16, top: 30, bottom: 28 },
    legend: { top: 0, textStyle: { color: t.label, fontSize: 11 }, icon: "roundRect" },
    tooltip: { trigger: "axis", backgroundColor: t.tooltipBg, borderWidth: 0, textStyle: { color: t.ink, fontSize: 12 } },
    xAxis: { type: "time", axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.label, fontSize: 11 } },
    yAxis: { type: "value", name: cfg.numeric ? "AQI" : "band", nameTextStyle: { color: t.label, fontSize: 10 }, axisLabel: { color: t.label, fontSize: 11 }, splitLine: { lineStyle: { color: t.split } } },
    series: selected.map((c, i) => ({
      name: c, type: "line", showSymbol: false, smooth: true,
      data: (data[c] ?? []).map((r) => {
        const v = cfg.numeric ? (r[aqiKey as keyof DailyRow] as number | null)
          : (r.eu_band ? cfg.bands.findIndex((b) => b.label === r.eu_band) : null);
        return [r.date, v];
      }),
      lineStyle: { color: LINE[i % LINE.length], width: 1.5 }, itemStyle: { color: LINE[i % LINE.length] }, connectNulls: false,
    })),
  } as EChartsCoreOption), [selected, data, aqiKey, cfg, t]);

  return (
    <section className="card p-5">
      <div className="mb-3"><SectionTitle icon={BarChart3}>Compare cities</SectionTitle></div>
      <div className="mb-3 flex flex-wrap gap-2">
        {available.map((c) => (
          <button
            key={c}
            onClick={() => toggle(c)}
            className={`rounded-full border px-3 py-1 text-xs ${
              selected.includes(c) ? "border-accent bg-accent/10 text-accent" : "border-border text-muted hover:bg-surface-2"
            }`}
          >
            {c}
          </button>
        ))}
      </div>
      {selected.length ? <EChart option={option} height={260} /> : <p className="py-8 text-center text-sm text-muted">Select cities to compare.</p>}
    </section>
  );
}
