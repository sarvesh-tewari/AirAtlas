// Shared date formatting. All user-facing dates render as "13 June 2026".

// Date-only values (e.g. "2026-06-12") format in UTC so the calendar day never shifts.
export function formatDate(d: string | number | Date): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  }).format(new Date(d));
}

// A full timestamp (UTC ISO) shown in IST, e.g. "13 June 2026, 14:30 IST" — the natural
// reference for an India air-quality dashboard.
export function formatDateTimeIST(iso: string): string {
  const d = new Date(iso);
  const date = new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata",
  }).format(d);
  const time = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata",
  }).format(d);
  return `${date}, ${time} IST`;
}

// Time-only in IST, e.g. "14:00 IST", for the rolling-24h headline "as of" label.
export function formatTimeIST(iso: string): string {
  const time = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata",
  }).format(new Date(iso));
  return `${time} IST`;
}

// ECharts axis-trigger tooltip with a "13 June 2026" header (the rest of the rows keep the
// default marker + series name + value layout).
export function dateAxisTooltip() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (params: any[]): string => {
    const head = `<div style="font-weight:600;margin-bottom:2px">${formatDate(params[0].axisValue)}</div>`;
    const rows = params
      .filter((p) => p.value?.[1] != null)
      .map((p) => `<div>${p.marker}${p.seriesName ? p.seriesName + ": " : ""}${Math.round(p.value[1] * 10) / 10}</div>`)
      .join("");
    return head + rows;
  };
}
