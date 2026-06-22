import { useEffect, useMemo, useState } from "react";
import type { EChartsCoreOption } from "echarts";
import { BarChart3, X } from "lucide-react";
import { EChart } from "./EChart";
import { chartTheme } from "../lib/chartTheme";
import { dateAxisTooltip } from "../lib/format";
import { SectionTitle } from "./SectionTitle";
import { Combobox } from "./Combobox";
import { STANDARDS, type StandardId } from "../lib/standards";
import { fetchDailyHistory, type DailyRow } from "../lib/data";

const LINE = ["#24426b", "#ef4444", "#10b981", "#f59e0b", "#a855f7", "#0ea5e9"];

export function Compare({
  available,
  current,
  standard,
  dark,
}: {
  available: string[];
  current: string;
  standard: StandardId;
  dark: boolean;
}) {
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
      if (!data[c])
        fetchDailyHistory(c)
          .then((rows) => setData((d) => ({ ...d, [c]: rows })))
          .catch(() => {});
    });
  }, [selected, data]);

  function add(c: string) {
    setSelected((s) => (s.includes(c) || s.length >= 6 ? s : [...s, c]));
  }
  function remove(c: string) {
    setSelected((s) => s.filter((x) => x !== c));
  }

  const aqiKey = standard === "us" ? "aqi_us" : "aqi_naqi";
  const option = useMemo(
    () =>
      ({
        grid: { left: 44, right: 16, top: 30, bottom: 28 },
        legend: { top: 0, textStyle: { color: t.label, fontSize: 11 }, icon: "roundRect" },
        tooltip: {
          trigger: "axis",
          formatter: dateAxisTooltip(),
          backgroundColor: t.tooltipBg,
          borderWidth: 0,
          textStyle: { color: t.ink, fontSize: 12 },
        },
        xAxis: {
          type: "time",
          axisLine: { lineStyle: { color: t.axis } },
          axisLabel: { color: t.label, fontSize: 11 },
        },
        yAxis: {
          type: "value",
          name: cfg.numeric ? "AQI" : "band",
          nameTextStyle: { color: t.label, fontSize: 10 },
          axisLabel: { color: t.label, fontSize: 11 },
          splitLine: { lineStyle: { color: t.split } },
        },
        series: selected.map((c, i) => ({
          name: c,
          type: "line",
          showSymbol: false,
          smooth: true,
          data: (data[c] ?? []).map((r) => {
            const v = cfg.numeric
              ? (r[aqiKey as keyof DailyRow] as number | null)
              : r.eu_band
                ? cfg.bands.findIndex((b) => b.label === r.eu_band)
                : null;
            return [r.date, v];
          }),
          lineStyle: { color: LINE[i % LINE.length], width: 1.5 },
          itemStyle: { color: LINE[i % LINE.length] },
          connectNulls: false,
        })),
      }) as EChartsCoreOption,
    [selected, data, aqiKey, cfg, t],
  );

  return (
    <section className="card p-5">
      <div className="mb-3">
        <SectionTitle
          icon={BarChart3}
          color="#db2777"
          eyebrow="Side by side"
          info="Multiple cities' AQI on one chart; add cities with the picker."
        >
          Compare cities
        </SectionTitle>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {selected.map((c, i) => (
          <span
            key={c}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-soft/60 py-1 pl-2.5 pr-1.5 text-xs text-heading"
          >
            <span className="h-2 w-2 rounded-full" style={{ background: LINE[i % LINE.length] }} />
            {c}
            <button
              onClick={() => remove(c)}
              aria-label={`Remove ${c}`}
              className="rounded-full p-0.5 text-muted hover:bg-border hover:text-heading"
            >
              <X size={12} />
            </button>
          </span>
        ))}
        {selected.length < 6 && (
          <Combobox
            value=""
            triggerLabel="+ Add city"
            placeholder="Search cities…"
            ariaLabel="Add a city to compare"
            options={available
              .filter((c) => !selected.includes(c))
              .map((c) => ({ value: c, label: c }))}
            onChange={add}
          />
        )}
      </div>
      {selected.length ? (
        <EChart option={option} height={260} ariaLabel="AQI comparison across selected cities" />
      ) : (
        <p className="py-8 text-center text-sm text-body">Select cities to compare.</p>
      )}
    </section>
  );
}
