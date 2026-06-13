import { Info } from "lucide-react";
import { Combobox, type Option } from "./Combobox";
import { Logo } from "./Logo";
import type { StandardId } from "../lib/standards";

export function TopBar({
  cities, city, onCity, standard, onStandard,
  dark, onToggleTheme, page, onNav,
}: {
  cities: Option[];
  city: string;
  onCity: (c: string) => void;
  standard: StandardId;
  onStandard: (s: StandardId) => void;
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
        <button onClick={() => onNav("dashboard")} aria-label="AirAtlas home" className="text-[19px]">
          <Logo variant="wordmark" />
        </button>

        {/* City + standard controls only apply to the dashboard data view - hide on About. */}
        {page === "dashboard" && (
          <>
            <Combobox value={city} options={cities} onChange={onCity} ariaLabel="Select city" placeholder="Search cities…" />

            <div role="group" aria-label="AQI standard" className="inline-flex overflow-hidden rounded-lg border border-border text-xs">
              {standards.map((s) => (
                <button
                  key={s.id}
                  onClick={() => onStandard(s.id)}
                  aria-pressed={standard === s.id}
                  className={`px-3 py-1.5 transition-colors ${
                    standard === s.id ? "bg-accent text-white" : "text-body hover:bg-bg-soft"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>

            <span className="group relative inline-flex">
              <button
                aria-label="Why do the standards show different numbers?"
                className="rounded-full p-1 text-muted hover:text-heading"
              >
                <Info size={16} />
              </button>
              <span
                role="tooltip"
                className="pointer-events-none absolute left-0 top-full z-30 mt-2 w-72 rounded-lg border border-border bg-surface p-3 text-xs leading-relaxed text-body opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
              >
                Each standard computes a <span className="text-heading">different number</span> from the
                same measured concentrations, using different breakpoints, units and averaging windows. So
                the index and even the dominant pollutant can differ across NAQI / US / EU. The raw
                concentrations don't change; only the formula does.
              </span>
            </span>
          </>
        )}

        <nav className="ml-auto flex items-center gap-1 text-sm">
          <button
            onClick={() => onNav("dashboard")}
            aria-current={page === "dashboard" ? "page" : undefined}
            className={`rounded-lg px-2.5 py-1.5 ${page === "dashboard" ? "text-heading" : "text-body hover:text-heading"}`}
          >
            Dashboard
          </button>
          <button
            onClick={() => onNav("methodology")}
            aria-current={page === "methodology" ? "page" : undefined}
            className={`rounded-lg px-2.5 py-1.5 ${page === "methodology" ? "text-heading" : "text-body hover:text-heading"}`}
          >
            About
          </button>
          <button
            onClick={onToggleTheme}
            aria-label="Toggle theme"
            className="ml-1 rounded-lg border border-border px-2 py-1.5 text-body hover:text-heading"
          >
            {dark ? "☀" : "☾"}
          </button>
        </nav>
      </div>
    </header>
  );
}
