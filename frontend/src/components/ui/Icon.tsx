import type { ReactNode } from "react";

const PATHS: Record<string, ReactNode> = {
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  plus: <path d="M12 5v14M5 12h14" />,
  x: <path d="M6 6l12 12M18 6L6 18" />,
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V6a1 1 0 011-1h9" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  trash: <path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12" />,
  book: (
    <>
      <path d="M5 19.5V5.5A1.5 1.5 0 016.5 4H19v14H6.5A1.5 1.5 0 005 19.5z" />
      <path d="M5 19.5A1.5 1.5 0 006.5 21H19" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3 20c.4-3.3 2.9-5.2 6-5.2s5.6 1.9 6 5.2" />
      <path d="M16 5.6a3.2 3.2 0 010 5.8M18 15c1.8.6 3 2.2 3.2 4.6" />
    </>
  ),
  trend: <path d="M4 17l5-5 4 3 7-8M15 7h5v5" />,
  upload: <path d="M12 16V5M7.5 9.5L12 5l4.5 4.5M5 19h14" />,
  pencil: <path d="M4 20l1-4.2L16.5 4.3a1.8 1.8 0 012.6 0l.6.6a1.8 1.8 0 010 2.6L8.2 19z" />,
  play: <path d="M8 5l11 7-11 7z" />,
  lock: (
    <>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 018 0v3" />
    </>
  ),
  flag: <path d="M6 21V4M6 5h11l-2 4 2 4H6" />,
  logout: <path d="M10 5H6a1 1 0 00-1 1v12a1 1 0 001 1h4M15 8l4 4-4 4M19 12H9" />,
  calendar: (
    <>
      <rect x="4" y="6" width="16" height="14" rx="2" />
      <path d="M4 11h16M9 4v4M15 4v4" />
    </>
  ),
  alert: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 8v4.5M12 16v.3" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5M12 8v.3" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="0.8" />
    </>
  ),
  list: <path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" />,
  chevron: <path d="M6 9l6 6 6-6" />,
  chart: <path d="M5 20V10M12 20V4M19 20v-6" />,
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, small = false }: { name: IconName; small?: boolean }) {
  return (
    <svg
      className={small ? "icon icon-sm" : "icon"}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

/** The SkillTrace mark: a mastery trace climbing to a goal. */
export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 28 28" aria-hidden="true">
      <rect width="28" height="28" rx="8" fill="var(--brand)" />
      <path d="M6.5 19.5l5-5.2 3.4 2.9 6.6-7.7" fill="none" stroke="var(--brand-ink)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="21.5" cy="9.5" r="2.1" fill="var(--brand-ink)" />
    </svg>
  );
}
