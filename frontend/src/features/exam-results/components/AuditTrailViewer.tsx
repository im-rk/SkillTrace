import type { AuditEvent } from "@/features/exam-results/api/results.api";

/** A simple chronological list is sufficient here -- the phase doc is
 * explicit that this doesn't need elaborate visualization. */
export function AuditTrailViewer({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) return <p>No events recorded for this session.</p>;

  return (
    <ol>
      {events.map((event, index) => (
        <li key={index}>
          <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString()}</time> — {event.type}
          {Object.keys(event.detail).length > 0 && <pre>{JSON.stringify(event.detail)}</pre>}
        </li>
      ))}
    </ol>
  );
}
