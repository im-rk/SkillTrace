"use client";

import { useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api-client";
import { resultsApi, type ExamResultRow } from "@/features/exam-results/api/results.api";
import { Meter } from "@/components/ui/Bits";
import { initials, pct } from "@/lib/format";

/** "View audit trail" isn't a link in the overview response (the overview deliberately never joins the results view
 * against exam_sessions live): it is resolved on click via a small, separate session lookup. */
export function ExamOverviewTable({ examId, rows }: { examId: string; rows: ExamResultRow[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="sr-only">Results per student</caption>
        <thead>
          <tr>
            <th scope="col">Student</th>
            <th scope="col" className="right">
              Score
            </th>
            <th scope="col">Mastery</th>
            <th scope="col" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <ExamOverviewRow key={row.user_id} examId={examId} row={row} />
          ))}
        </tbody>
      </table>
    </div>
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
      <th scope="row" style={{ textTransform: "none", letterSpacing: 0, fontSize: 14, color: "var(--ink)" }}>
        <span className="row" style={{ gap: 10, flexWrap: "nowrap" }}>
          <span className="avatar" aria-hidden="true">
            {initials(row.display_name)}
          </span>
          {row.display_name}
        </span>
      </th>
      <td className="right num" style={{ fontWeight: 650 }}>
        {row.total_score}
      </td>
      <td>
        {row.final_mastery !== null ? (
          <div className="bar-cell">
            <Meter value={row.final_mastery} label={`${row.display_name} mastery`} />
            <span className="num">{pct(row.final_mastery)}%</span>
          </div>
        ) : (
          "—"
        )}
      </td>
      <td className="right">
        {sessionId ? (
          <Link href={`/admin/exam-sessions/${sessionId}/audit-trail`} className="link small">
            View audit trail
          </Link>
        ) : (
          <button type="button" className="btn btn-ghost btn-sm" disabled={loading} onClick={resolveAuditTrail}>
            {loading ? "Loading…" : "Audit trail"}
          </button>
        )}
        {error && (
          <span role="alert" className="small" style={{ color: "var(--rust)", display: "block" }}>
            {error}
          </span>
        )}
      </td>
    </tr>
  );
}
