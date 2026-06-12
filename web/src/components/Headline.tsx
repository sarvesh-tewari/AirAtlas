import { Gauge } from "./Gauge";
import { STANDARDS, bandByLabel, type StandardId } from "../lib/standards";

export interface HeadlineVM {
  city: string;
  index: number | null;
  band: string | null;
  category: string | null;
  dominantLabel: string | null;
  dominantValue: number | null;
  dominantUnit: string | null;
  stale: boolean;
  live: boolean;
  nStations: number;
}

export function Headline({ standard, vm }: { standard: StandardId; vm: HeadlineVM }) {
  const color = vm.category ? bandByLabel(standard, vm.category).color : "var(--muted)";
  return (
    <section className="card overflow-hidden">
      {vm.stale && (
        <div className="bg-amber-500/15 px-5 py-2 text-sm text-amber-700 dark:text-amber-300">
          Showing the last available reading — today's live data isn't in yet.
        </div>
      )}
      <div className="grid gap-6 p-6 sm:grid-cols-[260px_1fr] sm:items-center">
        <div className="flex justify-center">
          {vm.index != null ? (
            <Gauge standard={standard} index={vm.index} />
          ) : vm.band ? (
            <div className="flex flex-col items-center gap-2 py-6">
              <span className="font-display text-2xl" style={{ color }}>{vm.band}</span>
              <span className="text-xs text-faint">EU EAQI band</span>
            </div>
          ) : (
            <div className="py-10 text-muted">No data</div>
          )}
        </div>

        <div>
          <div className="font-display text-3xl text-ink">{vm.city}</div>
          <div className="mt-1 text-sm text-muted">{STANDARDS[standard].name}</div>
          {vm.category && (
            <div className="mt-3 inline-flex items-center rounded-full px-3 py-1 text-sm font-medium"
                 style={{ background: `${color}1f`, color }}>
              {vm.category}
            </div>
          )}
          {vm.dominantLabel && (
            <p className="mt-3 text-sm text-muted">
              Dominant pollutant <span className="font-medium text-ink">{vm.dominantLabel}</span>
              {vm.dominantValue != null && (
                <> · {Math.round(vm.dominantValue * 10) / 10} {vm.dominantUnit}</>
              )}
            </p>
          )}
          <p className="mt-2 text-xs text-faint">
            {vm.nStations > 0 ? `${vm.nStations} station${vm.nStations > 1 ? "s" : ""}` : ""}
            {vm.live ? " · live (CPCB)" : " · latest available"}
          </p>
        </div>
      </div>
    </section>
  );
}
