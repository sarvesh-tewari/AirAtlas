import { CloudFog, Wind, Factory, Flame, Sun, Car, FlaskConical, Atom, type LucideIcon } from "lucide-react";
import { POLLUTANT_LABELS } from "../lib/standards";
import { SectionTitle } from "./SectionTitle";

// Context-specific, restrained icons (sources/nature of each pollutant).
const ICONS: Record<string, { icon: LucideIcon; color: string }> = {
  pm25: { icon: CloudFog, color: "#6366f1" },   // fine particulate / haze
  pm10: { icon: Wind, color: "#0ea5e9" },       // coarse dust
  no2: { icon: Factory, color: "#d97706" },     // combustion / traffic
  so2: { icon: Flame, color: "#a855f7" },       // fuel burning
  o3: { icon: Sun, color: "#10b981" },          // photochemical
  co: { icon: Car, color: "#ef4444" },          // vehicle exhaust
  nh3: { icon: FlaskConical, color: "#0d9488" },
};

export interface PollutantVM {
  key: string;
  value: number;
  unit: string;
  subindex: number | null;
  dominant: boolean;
}

export function PollutantCards({ pollutants }: { pollutants: PollutantVM[] }) {
  if (pollutants.length === 0) return null;
  return (
    <section>
      <div className="mb-1"><SectionTitle icon={Atom} color="#0284c7" eyebrow="In the air" info="The individual concentrations behind the AQI; the dominant pollutant (the one setting the index) is highlighted. Units µg/m³, CO in mg/m³.">Pollutants</SectionTitle></div>
      <p className="mb-3 text-xs text-muted">
        These are the measured concentrations. The AQI index is <em>derived</em> from them, so it
        differs by standard, while these values stay the same.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {pollutants.map((p) => (
          <div
            key={p.key}
            className="card p-4"
            style={p.dominant ? { borderColor: "var(--accent)" } : undefined}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-medium text-body">
                {(() => {
                  const m = ICONS[p.key];
                  return m ? <m.icon size={15} color={m.color} strokeWidth={2} /> : null;
                })()}
                {POLLUTANT_LABELS[p.key] ?? p.key}
              </span>
              {p.dominant && <span className="text-[10px] uppercase tracking-wide text-accent-text">dom</span>}
            </div>
            <div className="mt-1 font-display text-2xl text-heading">{Math.round(p.value * 10) / 10}</div>
            <div className="text-[11px] text-muted">{p.unit}</div>
            {p.subindex != null && (
              <div className="mt-1 text-[11px] text-body">sub-index {p.subindex}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
