"use client";

import { useState } from "react";
import type { PracticeQuestion } from "@/features/practice/api/practice.api";
import { DifficultyChip, typeLabel } from "@/components/ui/Chip";

/** One adaptive question. The same card is kept (disabled) while the feedback is shown beneath it. */
export function PracticeQuestionCard({
  question,
  submitting,
  locked,
  onSubmit,
}: {
  question: PracticeQuestion;
  submitting: boolean;
  locked: boolean;
  onSubmit: (answer: string) => void;
}) {
  const [answer, setAnswer] = useState("");

  return (
    <fieldset className="q-card card-pad" disabled={submitting || locked} data-difficulty={question.difficulty}>
      <legend>{question.prompt}</legend>
      <div className="row" style={{ marginBottom: 18 }}>
        <DifficultyChip difficulty={question.difficulty} />
        <span className="muted small">{typeLabel(question.question_type)}</span>
      </div>

      {question.question_type === "multiple_choice" && (
        <div className="choices">
          {question.content.choices?.map((choice) => (
            <label key={choice.id} className="choice">
              <input type="radio" name={question.id} value={choice.id} checked={answer === choice.id} onChange={(e) => setAnswer(e.target.value)} />
              {choice.text}
            </label>
          ))}
        </div>
      )}

      {question.question_type === "true_false" && (
        <div className="choices">
          {["true", "false"].map((value) => (
            <label key={value} className="choice">
              <input type="radio" name={question.id} value={value} checked={answer === value} onChange={(e) => setAnswer(e.target.value)} />
              {value === "true" ? "True" : "False"}
            </label>
          ))}
        </div>
      )}

      {question.question_type === "text_input" && (
        <input
          type="text"
          className="input"
          aria-label="Your answer"
          placeholder="Type your answer"
          autoComplete="off"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          style={{ minHeight: 48, fontSize: 17 }}
        />
      )}

      {!locked && (
        <div className="form-actions" style={{ marginTop: 20 }}>
          <button type="button" className="btn btn-primary btn-lg" disabled={!answer.trim() || submitting} onClick={() => onSubmit(answer)}>
            {submitting ? "Checking…" : "Submit answer"}
          </button>
        </div>
      )}
    </fieldset>
  );
}
