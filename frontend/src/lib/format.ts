/** Mastery as a whole percent. */
export const pct = (value: number) => Math.round(value * 100);

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

const DATE = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });
const TIME = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

export const formatDate = (iso: string) => DATE.format(new Date(iso));
export const formatTime = (iso: string) => TIME.format(new Date(iso));

/** "Tue 14 Oct, 9:45 AM – 12:45 PM", or both ends when the exam spans days. */
export function formatWindow(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const sameDay = start.toDateString() === end.toDateString();
  return sameDay
    ? `${formatDate(startIso)}, ${formatTime(startIso)} – ${formatTime(endIso)}`
    : `${formatDate(startIso)}, ${formatTime(startIso)} – ${formatDate(endIso)}, ${formatTime(endIso)}`;
}

export function greeting(): string {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
