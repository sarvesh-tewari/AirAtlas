import { Combobox, type Option } from "./Combobox";
import type { StandardId } from "../lib/standards";

export function TopBar({
  cities, city, onCity, standard, onStandard, updatedLabel, source,
  dark, onToggleTheme, page, onNav,
}: {
  cities: Option[];
  city: string;
  onCity: (c: string) => void;
  standard: StandardId;
  onStandard: (s: StandardId) => void;
  updatedLabel: string | null;
  source: string | null;
  dark: boolean;
  onToggleTheme: () => void;
  page: "dashboard" | "methodology";
  onNav: (p: "dashboard" | "methodology") => void;
}) {
  const standards: { id: StandardId; label: string }[] = [
    { id: "naqi", label: "NAQI" },
    { id: "us", label: "US EPA" },
    { id: "eu", label: "EU" },
  ];
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
        <button onClick={() => onNav("dashboard")} className="font-display text-xl text-ink">
          Air<span className="text-accent">Atlas</span>
        </button>

        <Combobox value={city} options={cities} onChange={onCity} ariaLabel="Select city" placeholder="Search cities…" />

        <div className="inline-flex overflow-hidden rounded-lg border border-border text-xs">
          {standards.map((s) => (
            <button
              key={s.id}
              onClick={() => onStandard(s.id)}
              className={`px-3 py-1.5 transition-colors ${
                standard === s.id ? "bg-accent text-white" : "text-muted hover:bg-surface-2"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <nav className="ml-auto flex items-center gap-1 text-sm">
          <button
            onClick={() => onNav("dashboard")}
            className={`rounded-lg px-2.5 py-1.5 ${page === "dashboard" ? "text-ink" : "text-muted hover:text-ink"}`}
          >
            Dashboard
          </button>
          <button
            onClick={() => onNav("methodology")}
            className={`rounded-lg px-2.5 py-1.5 ${page === "methodology" ? "text-ink" : "text-muted hover:text-ink"}`}
          >
            Methodology
          </button>
          {updatedLabel && (
            <span className="ml-1 hidden text-xs text-faint sm:inline">
              {source === "cpcb" ? "CPCB" : source === "openaq" ? "OpenAQ" : ""} · {updatedLabel}
            </span>
          )}
          <button
            onClick={onToggleTheme}
            aria-label="Toggle theme"
            className="ml-1 rounded-lg border border-border px-2 py-1.5 text-muted hover:text-ink"
          >
            {dark ? "☀" : "☾"}
          </button>
        </nav>
      </div>
    </header>
  );
}
