"use client";

import { useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api-client";
import { resultsApi, type ExamResultRow } from "@/features/exam-results/api/results.api";

/** "View audit trail" isn't a link in the overview response (Phase 10
 * deliberately never joins mv_exam_results against exam_sessions live) --
 * it's resolved on click via a small, separate, live session lookup. */
export function ExamOverviewTable({ examId, rows }: { examId: string; rows: ExamResultRow[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Student</th>
          <th>Score</th>
          <th>Mastery</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <ExamOverviewRow key={row.user_id} examId={examId} row={row} />
        ))}
      </tbody>
    </table>
  );
}

function ExamOverviewRow({ examId, row }: { examId: string; row: ExamResultRow }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function resolveAuditTrail() {
    setError(null);
    setLoading(true);
    try {
      const { session_id } = await resultsApi.getSessionIdForStudent(examId, row.user_id);
      setSessionId(session_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not look up this student's session.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <tr>
      <td>{row.display_name}</td>
      <td>{row.total_score}</td>
      <td>{row.final_mastery !== null ? `${Math.round(row.final_mastery * 100)}%` : "—"}</td>
      <td>
        {sessionId ? (
          <Link href={`/admin/exam-sessions/${sessionId}/audit-trail`}>View audit trail</Link>
        ) : (
          <button type="button" disabled={loading} onClick={resolveAuditTrail}>
            {loading ? "Loading…" : "Audit trail"}
          </button>
        )}
        {error && <span role="alert">{error}</span>}
      </td>
    </tr>
  );
}
