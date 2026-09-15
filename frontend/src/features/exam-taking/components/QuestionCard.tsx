"use client";

import { useState } from "react";
import type { StudentExamQuestion } from "@/features/exam-taking/api/exam-taking.api";
import { useSubmitAnswer } from "@/features/exam-taking/hooks/useSubmitAnswer";

const PHASE_LABEL: Record<string, string> = {
  submitting: "Submitting…",
  processing: "Submitted — grading…",
  confirmed: "Answer recorded",
  failed: "Something went wrong — try submitting again",
};

export function QuestionCard({ sessionId, question }: { sessionId: string; question: StudentExamQuestion }) {
  const [answer, setAnswer] = useState("");
  const { phase, submit } = useSubmitAnswer(sessionId);

  return (
    <fieldset>
      <legend>{question.prompt}</legend>

      {question.question_type === "multiple_choice" &&
        question.content.choices?.map((choice) => (
          <label key={choice.id}>
            <input
              type="radio"
              name={question.question_id}
              value={choice.id}
              checked={answer === choice.id}
              onChange={(e) => setAnswer(e.target.value)}
            />
            {choice.text}
          </label>
        ))}

      {question.question_type === "true_false" && (
        <>
          <label>
            <input type="radio" name={question.question_id} value="true" onChange={(e) => setAnswer(e.target.value)} />
            True
          </label>
          <label>
            <input
              type="radio"
              name={question.question_id}
              value="false"
              onChange={(e) => setAnswer(e.target.value)}
            />
            False
          </label>
        </>
      )}

      {question.question_type === "text_input" && (
        <input type="text" value={answer} onChange={(e) => setAnswer(e.target.value)} />
      )}

      <button type="button" disabled={!answer || phase === "submitting"} onClick={() => submit(question.question_id, answer)}>
        Submit answer
      </button>
      {phase !== "idle" && <p role="status">{PHASE_LABEL[phase]}</p>}
    </fieldset>
  );
}
