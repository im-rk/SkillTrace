import { Meter } from "@/components/ui/Bits";
import { pct } from "@/lib/format";

/** Mastery as a big number over a bar, with a tick at the goal and the movement from the last answer. */
export function MasteryGauge({
  mastery,
  threshold,
  delta,
  answered,
  correct,
}: {
  mastery: number;
  threshold: number;
  delta: number | null;
  answered: number;
  correct: number;
}) {
  const value = pct(mastery);
  const goal = pct(threshold);
  return (
    <section className="mastery-panel" aria-label="Your mastery">
      <div className="row-between" style={{ alignItems: "flex-end", marginBottom: 14 }}>
        <div>
          <p className="eyebrow" style={{ marginBottom: 6 }}>
            Your mastery
          </p>
          <div className="row" style={{ gap: 12 }}>
            <span className="mastery-figure num">{value}%</span>
            {delta !== null && delta !== 0 && (
              <span className={`delta ${delta > 0 ? "up" : "down"}`} aria-label={`Changed by ${delta > 0 ? "plus" : "minus"} ${Math.abs(delta)} points`}>
                {delta > 0 ? "▲" : "▼"} {Math.abs(delta)}
              </span>
            )}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <p className="muted small">Goal {goal}%</p>
          <p className="muted small num">
            {correct} of {answered} correct
          </p>
        </div>
      </div>
      <Meter value={mastery} goal={threshold} large label="Mastery" />
    </section>
  );
}
