"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { examAdminApi, type AssignedQuestion } from "@/features/exam-admin/api/exam-admin.api";
import { questionBankApi, type Question } from "@/features/question-bank-admin/api/question-bank.api";

export function QuestionAssignmentPanel({ examId, skillId }: { examId: string; skillId: string }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selected, setSelected] = useState<Record<string, string>>({}); // question_id -> points
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    questionBankApi.list(skillId).then((loaded) => {
      if (!cancelled) setQuestions(loaded);
    });
    return () => {
      cancelled = true;
    };
  }, [skillId]);

  function toggle(questionId: string) {
    setSelected((current) => {
      const next = { ...current };
      if (questionId in next) {
        delete next[questionId];
      } else {
        next[questionId] = "1.0";
      }
      return next;
    });
  }

  async function handleAssign() {
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      const assignments: AssignedQuestion[] = Object.entries(selected).map(([questionId, points], index) => ({
        question_id: questionId,
        display_order: index + 1,
        points,
      }));
      await examAdminApi.assignQuestions(examId, assignments);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not assign questions.");
    } finally {
      setSubmitting(false);
    }
  }

  if (questions.length === 0) return <p>No questions in this skill yet.</p>;

  return (
    <div>
      <ul>
        {questions.map((q) => (
          <li key={q.id}>
            <label>
              <input type="checkbox" checked={q.id in selected} onChange={() => toggle(q.id)} />
              {q.prompt}
            </label>
            {q.id in selected && (
              <input
                type="number"
                step="0.5"
                min="0"
                value={selected[q.id]}
                onChange={(e) => setSelected((current) => ({ ...current, [q.id]: e.target.value }))}
                aria-label={`Points for ${q.prompt}`}
              />
            )}
          </li>
        ))}
      </ul>
      {error && <p role="alert">{error}</p>}
      {success && <p role="status">Questions assigned.</p>}
      <button type="button" disabled={submitting || Object.keys(selected).length === 0} onClick={handleAssign}>
        {submitting ? "Assigning…" : "Assign selected questions"}
      </button>
    </div>
  );
}
