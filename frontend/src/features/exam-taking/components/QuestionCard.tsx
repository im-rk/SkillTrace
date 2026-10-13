"use client";

import { useEffect, useState } from "react";
import type { StudentExamQuestion } from "@/features/exam-taking/api/exam-taking.api";
import { useSubmitAnswer } from "@/features/exam-taking/hooks/useSubmitAnswer";
import { Icon } from "@/components/ui/Icon";

const PHASE_LABEL: Record<string, string> = {
  submitting: "Submitting…",
  processing: "Submitted — grading…",
  confirmed: "Answer recorded",
  failed: "Something went wrong — try submitting again",
};

export function QuestionCard({
  sessionId,
  question,
  index,
  total,
  onConfirmed,
}: {
  sessionId: string;
  question: StudentExamQuestion;
  index: number;
  total: number;
  onConfirmed: (questionId: string) => void;
}) {
  const [answer, setAnswer] = useState("");
  const { phase, submit, errorMessage } = useSubmitAnswer(sessionId);
  // An answer is final once accepted: the server takes one answer per question.
  const locked = phase === "processing" || phase === "confirmed";

  useEffect(() => {
    if (phase === "confirmed") onConfirmed(question.question_id);
  }, [phase, onConfirmed, question.question_id]);

  return (
    <fieldset className="q-card exam-q card-pad" disabled={locked} data-state={phase === "confirmed" ? "done" : "open"}>
      <legend>
        <span className="q-index">
          Question {index + 1} of {total}
        </span>
        {question.prompt}
      </legend>

      {question.question_type === "multiple_choice" && (
        <div className="choices">
          {question.content.choices?.map((choice) => (
            <label key={choice.id} className="choice">
              <input type="radio" name={question.question_id} value={choice.id} checked={answer === choice.id} onChange={(e) => setAnswer(e.target.value)} />
              {choice.text}
            </label>
          ))}
        </div>
      )}

      {question.question_type === "true_false" && (
        <div className="choices">
          <label className="choice">
            <input type="radio" name={question.question_id} value="true" checked={answer === "true"} onChange={(e) => setAnswer(e.target.value)} />
            True
          </label>
          <label className="choice">
            <input type="radio" name={question.question_id} value="false" checked={answer === "false"} onChange={(e) => setAnswer(e.target.value)} />
            False
          </label>
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
        />
      )}

      <div className="row" style={{ marginTop: 18 }}>
        <button type="button" className="btn btn-primary" disabled={!answer || phase === "submitting"} onClick={() => submit(question.question_id, answer)}>
          Submit answer
        </button>
        {phase !== "idle" && phase !== "failed" && (
          <span role="status" className={`chip ${phase === "confirmed" ? "chip-ok" : "chip-info"}`}>
            {phase === "confirmed" && <Icon name="check" small />}
            {PHASE_LABEL[phase]}
          </span>
        )}
        {phase === "failed" && (
          <span role="alert" className="chip chip-bad">
            {errorMessage ?? PHASE_LABEL.failed}
          </span>
        )}
      </div>
    </fieldset>
  );
}
