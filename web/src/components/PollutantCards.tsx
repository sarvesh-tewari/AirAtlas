import { CloudFog, Wind, Factory, Flame, Sun, Car, FlaskConical, Atom, type LucideIcon } from "lucide-react";
import { POLLUTANT_LABELS } from "../lib/standards";
import { SectionTitle } from "./SectionTitle";

// Context-specific, restrained icons (sources/nature of each pollutant).
const ICONS: Record<string, LucideIcon> = {
  pm25: CloudFog,  // fine particulate / haze
  pm10: Wind,      // coarse dust
  no2: Factory,    // combustion / traffic
  so2: Flame,      // fuel burning
  o3: Sun,         // photochemical
  co: Car,         // vehicle exhaust
  nh3: FlaskConical,
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
      <div className="mb-3"><SectionTitle icon={Atom}>Pollutants</SectionTitle></div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {pollutants.map((p) => (
          <div
            key={p.key}
            className="card p-4"
            style={p.dominant ? { borderColor: "var(--accent)" } : undefined}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-medium text-muted">
                {(() => { const Icon = ICONS[p.key]; return Icon ? <Icon size={15} className="text-faint" strokeWidth={1.75} /> : null; })()}
                {POLLUTANT_LABELS[p.key] ?? p.key}
              </span>
              {p.dominant && <span className="text-[10px] uppercase tracking-wide text-accent">dom</span>}
            </div>
            <div className="mt-1 font-display text-2xl text-ink">{Math.round(p.value * 10) / 10}</div>
            <div className="text-[11px] text-faint">{p.unit}</div>
            {p.subindex != null && (
              <div className="mt-1 text-[11px] text-muted">sub-index {p.subindex}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
