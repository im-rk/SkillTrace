import type { StudentExamResult } from "@/features/exam-results/api/results.api";

export function StudentResultCard({ result }: { result: StudentExamResult }) {
  return (
    <dl>
      <dt>Questions answered</dt>
      <dd>{result.questions_answered}</dd>
      <dt>Total score</dt>
      <dd>{result.total_score}</dd>
      <dt>Final mastery</dt>
      <dd>{result.final_mastery !== null ? `${Math.round(result.final_mastery * 100)}%` : "—"}</dd>
    </dl>
  );
}
