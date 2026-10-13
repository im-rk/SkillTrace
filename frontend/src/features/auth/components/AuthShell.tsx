import type { ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";

/** A hand-drawn-feeling mastery trace: the thing the product is about, shown instead of a stock illustration. */
function TraceDemo() {
  return (
    <svg className="trace-demo" viewBox="0 0 340 150" role="img" aria-label="A student's mastery rising over several answers toward a goal line">
      <line x1="12" y1="44" x2="328" y2="44" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" strokeDasharray="5 5" />
      <text x="14" y="36" fill="currentColor" fillOpacity="0.8" fontSize="11" fontWeight="600">
        Goal 85%
      </text>
      <path
        d="M16 118 L72 52 L118 98 L170 70 L224 36 L290 22"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {[
        [16, 118, true],
        [72, 52, true],
        [118, 98, false],
        [170, 70, true],
        [224, 36, true],
        [290, 22, true],
      ].map(([x, y, right], i) => (
        <circle
          key={i}
          cx={x as number}
          cy={y as number}
          r="5.5"
          fill={right ? "currentColor" : "var(--brand)"}
          stroke="currentColor"
          strokeWidth="2.2"
        />
      ))}
    </svg>
  );
}

export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="auth-split">
      <aside className="auth-aside">
        <div>
          <h2 className="title">See what each student actually knows.</h2>
          <p>
            A score says how many answers were right. SkillTrace estimates the chance a student has mastered a skill, and updates it after every answer.
          </p>
        </div>
        <TraceDemo />
        <ul>
          <li>
            <Icon name="check" />
            Practice that adapts its difficulty to the student.
          </li>
          <li>
            <Icon name="check" />
            Timed exams with a server-controlled clock.
          </li>
          <li>
            <Icon name="check" />
            Every estimate can be traced back to the answers behind it.
          </li>
        </ul>
      </aside>
      <main className="auth-main" style={{ padding: "48px 24px", maxWidth: "none" }}>
        <div className="auth-card">
          <h1 className="title">{title}</h1>
          <p className="muted" style={{ margin: "8px 0 28px" }}>
            {subtitle}
          </p>
          {children}
          <p className="muted small" style={{ marginTop: 24 }}>
            {footer}
          </p>
        </div>
      </main>
    </div>
  );
}
