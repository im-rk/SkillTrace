"use client";

import { useState, type ReactNode } from "react";
import { Icon, type IconName } from "@/components/ui/Icon";

export function EmptyState({ icon = "book", title, children, action }: { icon?: IconName; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <span className="icon-wrap">
        <Icon name={icon} />
      </span>
      <h3 className="h3">{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function Notice({
  tone = "info",
  children,
  role,
}: {
  tone?: "error" | "ok" | "warn" | "info";
  children: ReactNode;
  role?: "alert" | "status";
}) {
  const icon: IconName = tone === "ok" ? "check" : tone === "info" ? "info" : "alert";
  return (
    <div className={`notice notice-${tone}`} role={role ?? (tone === "error" ? "alert" : undefined)}>
      <Icon name={icon} />
      <div>{children}</div>
    </div>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value num">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

export function LoadingBlock({ lines = 3 }: { lines?: number }) {
  return (
    <div className="stack-sm" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: i === 0 ? 22 : 16, width: `${100 - i * 14}%` }} />
      ))}
    </div>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="btn btn-secondary btn-sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch {
          /* clipboard unavailable (insecure context); the code is still on screen */
        }
      }}
    >
      <Icon name={copied ? "check" : "copy"} small />
      {copied ? "Copied" : label}
    </button>
  );
}

/** Mastery (or any 0-1 value) as a bar with an optional goal tick. */
export function Meter({ value, goal, large = false, label }: { value: number; goal?: number; large?: boolean; label: string }) {
  const percent = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const reached = goal !== undefined && value >= goal;
  return (
    <div
      className={`meter ${large ? "meter-lg" : ""} ${reached ? "reached" : ""}`}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      aria-valuetext={`${percent}%`}
    >
      <span style={{ width: `${percent}%` }} />
      {goal !== undefined && <i className="meter-goal" style={{ left: `${Math.round(goal * 100)}%` }} title={`Goal ${Math.round(goal * 100)}%`} />}
    </div>
  );
}

/** A score ring: `value` 0-1 around the circle, a big label inside. */
export function Ring({ value, size = 132, children }: { value: number; size?: number; children: ReactNode }) {
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className="ring-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--brand)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - Math.min(1, Math.max(0, value)))}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="ring-label">{children}</div>
    </div>
  );
}
