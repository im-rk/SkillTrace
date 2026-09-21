import { pct } from "@/features/practice/api/practice.api";

/** Mastery as a bar that animates between values, with a tick at the mastery goal. */
export function MasteryGauge({ mastery, threshold }: { mastery: number; threshold: number }) {
  const value = pct(mastery);
  const goal = pct(threshold);
  const reached = mastery >= threshold;
  return (
    <div>
      <div
        role="meter"
        aria-label="Mastery"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        aria-valuetext={`${value}%`}
        style={{ position: "relative", height: 16, background: "#e5e7eb", borderRadius: 8, overflow: "hidden", maxWidth: 480 }}
      >
        <div
          style={{
            width: `${value}%`,
            height: "100%",
            background: reached ? "#16a34a" : "#2563eb",
            transition: "width 600ms ease, background 600ms ease",
          }}
        />
        <div style={{ position: "absolute", left: `${goal}%`, top: 0, bottom: 0, width: 2, background: "#111827" }} />
      </div>
      <small>
        Mastery {value}% (goal {goal}%)
      </small>
    </div>
  );
}
