import { CloudSun } from "lucide-react";
import { SectionTitle } from "./SectionTitle";

export interface WeatherVM {
  temp_c: number | null;
  rh_pct: number | null;
  precip_mm: number | null;
  wind_ms: number | null;
}

function Stat({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-lg text-muted" aria-hidden>{icon}</span>
      <div>
        <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
        <div className="font-display text-lg text-heading">{value}</div>
      </div>
    </div>
  );
}

export function WeatherStrip({ vm }: { vm: WeatherVM | null }) {
  if (!vm) return null;
  const n = (v: number | null, d = 0) => (v == null ? "-" : (Math.round(v * 10 ** d) / 10 ** d).toString());
  return (
    <section className="card p-5">
      <div className="mb-3"><SectionTitle icon={CloudSun} color="#0891b2" eyebrow="Conditions" info="Current conditions from Open-Meteo, shown alongside air quality since weather drives pollution.">Weather</SectionTitle></div>
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
        <Stat label="Temp" value={`${n(vm.temp_c, 1)}°C`} icon="🌡" />
        <Stat label="Humidity" value={`${n(vm.rh_pct)}%`} icon="💧" />
        <Stat label="Rain" value={`${n(vm.precip_mm, 1)} mm`} icon="🌧" />
        <Stat label="Wind" value={`${n(vm.wind_ms, 1)} m/s`} icon="🌬" />
      </div>
    </section>
  );
}
