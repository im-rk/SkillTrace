"use client";

import { ApiError } from "@/lib/api-client";
import { questionBankApi, type Question } from "@/features/question-bank-admin/api/question-bank.api";

export function QuestionList({ questions, onDeleted }: { questions: Question[]; onDeleted: () => void }) {
  async function handleDelete(id: string) {
    try {
      await questionBankApi.delete(id);
      onDeleted();
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : "Could not delete this question.");
    }
  }

  if (questions.length === 0) return <p>No questions yet.</p>;

  return (
    <ul>
      {questions.map((q) => (
        <li key={q.id}>
          <span>{q.prompt}</span>
          <span> ({q.question_type}, {q.difficulty})</span>
          <button type="button" data-variant="danger" onClick={() => handleDelete(q.id)}>
            Delete
          </button>
        </li>
      ))}
    </ul>
  );
}
