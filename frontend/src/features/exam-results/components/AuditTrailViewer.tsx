import type { AuditEvent } from "@/features/exam-results/api/results.api";
import { EmptyState } from "@/components/ui/Bits";

const LABEL: Record<string, string> = {
  answer_submitted: "Answer submitted",
  submitted: "Exam submitted",
  auto_submitted: "Exam auto-submitted (time ran out)",
  started: "Exam started",
  paused: "Connection lost — clock paused",
  resumed: "Reconnected — clock resumed",
};

/** A chronological timeline of what happened in one student's exam session. */
export function AuditTrailViewer({ events }: { events: AuditEvent[] }) {
  if (events.length === 0)
    return (
      <div className="card">
        <EmptyState icon="list" title="No events recorded">
          Nothing was recorded for this session.
        </EmptyState>
      </div>
    );

  return (
    <ol className="card divided" style={{ listStyle: "none" }}>
      {events.map((event, index) => (
        <li key={index} className="q-row" style={{ alignItems: "start" }}>
          <div>
            <div style={{ fontWeight: 600 }}>
              {LABEL[event.type] ?? event.type}
              <span className="sr-only"> ({event.type})</span>
            </div>
            <div className="muted small mono">{event.type}</div>
            {Object.keys(event.detail).length > 0 && (
              <pre className="mono small muted" style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(event.detail)}
              </pre>
            )}
          </div>
          <time dateTime={event.timestamp} className="muted small num">
            {new Date(event.timestamp).toLocaleString()}
          </time>
        </li>
      ))}
    </ol>
  );
}
