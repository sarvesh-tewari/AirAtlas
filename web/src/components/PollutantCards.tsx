import { POLLUTANT_LABELS } from "../lib/standards";

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
      <h2 className="mb-3 font-display text-lg text-ink">Pollutants</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {pollutants.map((p) => (
          <div
            key={p.key}
            className="card p-4"
            style={p.dominant ? { borderColor: "var(--accent)" } : undefined}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted">{POLLUTANT_LABELS[p.key] ?? p.key}</span>
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
