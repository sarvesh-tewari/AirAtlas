export const STALE_AFTER_DAYS = 30;

export function ageInDays(date: string | null): number | null {
  if (!date) return null;

  const ms = Date.now() - new Date(`${date.slice(0, 10)}T00:00:00Z`).getTime();

  return ms >= 0 ? Math.floor(ms / 8.64e7) : 0;
}

export function isStale(date: string | null): boolean {
  const age = ageInDays(date);
  return age != null && age > STALE_AFTER_DAYS;
}
