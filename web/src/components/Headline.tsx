import { Clock } from "lucide-react";
import { Gauge } from "./Gauge";
import { STANDARDS, bandByLabel, type StandardId } from "../lib/standards";
import { formatDate, formatDateTimeIST, formatTimeIST } from "../lib/format";
import { InfoDot } from "./SectionTitle";
import { STALE_AFTER_DAYS, ageInDays } from "../lib/freshness";

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
  updatedUtc: string | null;
  lastDate: string | null;
  asOfDate: string | null; // date the SHOWN reading is actually from (may be older than lastDate)
  source: string | null;
}

function agoText(days: number): string {
  if (days < 1) return "today";
  if (days === 1) return "yesterday";
  if (days < 60) return `${days} days ago`;
  const months = Math.round(days / 30);
  return months < 12
    ? `${months} months ago`
    : `${Math.round(days / 365)}+ years ago`;
}

export function Headline({
  standard,
  vm,
  loading = false,
}: {
  standard: StandardId;
  vm: HeadlineVM;
  loading?: boolean;
}) {
  const color = vm.category
    ? bandByLabel(standard, vm.category).color
    : "var(--muted)";
  // Flat category tint: the hero fills with a flat wash of the current AQI category colour
  // (no gradient - per the design system), with a matching tinted border.
  const wash = vm.category
    ? {
        background: `color-mix(in srgb, ${color} 12%, var(--surface))`,
        borderColor: `${color}55`,
      }
    : undefined;
  // The shown reading's own date (asOfDate) — may be older than the last row when a monitor has
  // gone quiet. A live reading shows a full IST timestamp; history shows that reading's date.
  const dataDate = vm.asOfDate ?? vm.lastDate;

  const updatedText =
    vm.live && vm.updatedUtc
      ? formatDateTimeIST(vm.updatedUtc)
      : dataDate
        ? formatDate(dataDate)
        : null;
  const sourceLabel =
    vm.source === "cpcb" ? "CPCB" : vm.source === "openaq" ? "OpenAQ" : null;
  const isRolling = vm.live && vm.source === "openaq";
  const hoursAgo =
    vm.live && vm.updatedUtc
      ? Math.max(
          0,
          Math.round((Date.now() - new Date(vm.updatedUtc).getTime()) / 3.6e6),
        )
      : null;
  const age = vm.live ? null : ageInDays(vm.asOfDate);
  const veryStale = age != null && age > STALE_AFTER_DAYS;

  const notice = veryStale
    ? `This city's monitor last reported a valid reading${updatedText ? ` on ${updatedText}` : ""} (${agoText(age!)}). Shown for reference only — it may not reflect current air quality.`
    : isRolling
      ? null
      : !vm.stale
        ? null
        : vm.live
          ? `Live reading may be delayed. Last updated ${updatedText ?? "recently"}.`
          : `Live data (CPCB) is currently unavailable, so this shows the latest published day${updatedText ? `, ${updatedText}` : ""}. History updates daily from OpenAQ.`;
  return (
    <section className="card overflow-hidden" style={wash}>
      {notice && (
        <div
          className="flex items-center gap-2 border-b px-6 py-2 text-xs"
          style={
            veryStale
              ? {
                  background: "color-mix(in srgb, #C8841f 14%, var(--surface))",
                  borderColor: "#C8841f55",
                  color: "var(--heading)",
                }
              : { borderColor: "var(--border)", color: "var(--body)" }
          }
        >
          <Clock size={13} aria-hidden />
          {notice}
        </div>
      )}
      <div className="grid gap-6 p-6 sm:grid-cols-[260px_1fr] sm:items-center">
        <div
          className="flex flex-col items-center gap-2"
          style={
            veryStale ? { opacity: 0.45, filter: "grayscale(0.7)" } : undefined
          }
        >
          {vm.index != null ? (
            <Gauge standard={standard} index={vm.index} />
          ) : vm.band ? (
            <div className="flex flex-col items-center gap-2 py-6">
              <span className="font-display text-2xl" style={{ color }}>
                {vm.band}
              </span>
              <span className="text-xs text-muted">EU EAQI band</span>
            </div>
          ) : loading ? (
            <div className="flex flex-col items-center gap-3 py-10 text-body">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-accent" />
              <span className="text-sm">Loading…</span>
            </div>
          ) : (
            <div className="py-10 text-body">No data for this selection</div>
          )}
        </div>

        <div>
          <div className="font-display text-3xl text-heading">{vm.city}</div>
          <div className="mt-1 text-sm text-body">
            {STANDARDS[standard].name}
          </div>
          {vm.category && (
            <div
              className="mt-3 inline-flex items-center rounded-full px-3 py-1 text-sm font-medium"
              style={{ background: `${color}1f`, color }}
            >
              {vm.category}
            </div>
          )}
          {vm.dominantLabel && (
            <p className="mt-3 text-sm text-body">
              Dominant pollutant{" "}
              <span className="font-medium text-heading">
                {vm.dominantLabel}
              </span>
              {vm.dominantValue != null && (
                <>
                  {" "}
                  · {Math.round(vm.dominantValue * 10) / 10} {vm.dominantUnit}
                </>
              )}
            </p>
          )}
          <p className="mt-2 text-xs text-muted">
            {vm.nStations > 0
              ? `${vm.nStations} station${vm.nStations > 1 ? "s" : ""} · `
              : ""}
            {sourceLabel ? `${sourceLabel} · ` : ""}
            {!updatedText
              ? vm.live
                ? "live"
                : "latest available"
              : isRolling
                ? `24h average · as of ${formatTimeIST(vm.updatedUtc ?? "")}${hoursAgo ? `, ${hoursAgo}h ago` : ""}`
                : vm.live
                  ? `updated ${updatedText}`
                  : `latest reading · ${updatedText}${age != null && age > 1 ? `, ${agoText(age)}` : ""}`}
            {isRolling && (
              <span className="ml-1">
                <InfoDot label="How the headline reading is computed">
                  A rolling average of the last 24 hours of hourly readings
                  (OpenAQ), labelled with the most recent hour. Updated every
                  few hours.
                </InfoDot>
              </span>
            )}
          </p>
        </div>
      </div>
    </section>
  );
}
