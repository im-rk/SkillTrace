"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { questionBankApi, type Difficulty, type Question, type QuestionContent } from "@/features/question-bank-admin/api/question-bank.api";
import { Chip, DifficultyChip, typeLabel } from "@/components/ui/Chip";
import { EmptyState, Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";

/** The correct answer in words, so an instructor can check a question (or an AI draft) at a glance. */
export function answerText(content: QuestionContent): string {
  if ("choices" in content) return content.choices.find((c) => c.id === content.correct_choice_id)?.text ?? "?";
  if ("case_sensitive" in content) return content.correct_answer;
  return content.correct_answer ? "True" : "False";
}

type Filter = "all" | Difficulty;

export function QuestionList({ questions, onDeleted }: { questions: Question[]; onDeleted: () => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(question: Question) {
    if (!window.confirm("Delete this question? Exams that already use it keep their own copy.")) return;
    try {
      await questionBankApi.delete(question.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not delete this question.");
    }
  }

  const counts = {
    all: questions.length,
    easy: questions.filter((q) => q.difficulty === "easy").length,
    medium: questions.filter((q) => q.difficulty === "medium").length,
    hard: questions.filter((q) => q.difficulty === "hard").length,
  };
  const visible = filter === "all" ? questions : questions.filter((q) => q.difficulty === filter);

  return (
    <div>
      <div className="card-head">
        <div className="segmented" role="group" aria-label="Filter by difficulty">
          {(["all", "easy", "medium", "hard"] as const).map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)} style={{ textTransform: "capitalize" }}>
              {f} <span className="muted num">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="card-body" style={{ paddingBottom: 0 }}>
          <Notice tone="error">{error}</Notice>
        </div>
      )}

      {visible.length === 0 ? (
        <EmptyState icon="book" title={questions.length === 0 ? "No questions yet" : `No ${filter} questions`}>
          {questions.length === 0 ? "Add a question, draft some with AI, or import a file to build this skill's bank." : "Try another filter."}
        </EmptyState>
      ) : (
        <ul className="divided" style={{ listStyle: "none" }}>
          {visible.map((q) => (
            <li key={q.id} className="q-row" data-testid="question-row">
              <div>
                <div className="prompt">{q.prompt}</div>
                <div className="q-meta">
                  <DifficultyChip difficulty={q.difficulty} />
                  <Chip dot={false}>{typeLabel(q.question_type)}</Chip>
                  {q.tags.includes("ai-generated") && <Chip tone="info" dot={false}>AI-drafted</Chip>}
                  <span className="muted small">
                    Answer: <b style={{ color: "var(--ink-2)" }}>{answerText(q.content)}</b>
                  </span>
                </div>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" aria-label={`Delete question: ${q.prompt}`} onClick={() => handleDelete(q)}>
                <Icon name="trash" small />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
