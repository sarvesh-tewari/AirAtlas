import { formatDateTimeIST } from "../lib/format";

// Site-wide "data last refreshed" line. This is the pipeline RUN time (when we last pulled),
// distinct from the per-city reading age shown in the headline. Driven by city_list.json's
// `refreshed_at`. Falls back to a generic line if the timestamp is missing (older data).
export function Footer({ refreshedAt }: { refreshedAt: string | null }) {
  return (
    <footer className="mt-2 border-t border-border">
      <div className="mx-auto max-w-6xl px-5 py-5 text-center text-xs text-muted">
        {refreshedAt
          ? `Last refreshed ${formatDateTimeIST(refreshedAt)}`
          : "Data refreshed daily"}
      </div>
    </footer>
  );
}
