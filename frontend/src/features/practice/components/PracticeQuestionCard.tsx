"use client";

import { useState } from "react";
import type { PracticeQuestion } from "@/features/practice/api/practice.api";

export function PracticeQuestionCard({
  question,
  submitting,
  onSubmit,
}: {
  question: PracticeQuestion;
  submitting: boolean;
  onSubmit: (answer: string) => void;
}) {
  const [answer, setAnswer] = useState("");

  return (
    <fieldset disabled={submitting}>
      <legend>{question.prompt}</legend>
      <p>
        <small>Difficulty: {question.difficulty}</small>
      </p>

      {question.question_type === "multiple_choice" &&
        question.content.choices?.map((choice) => (
          <label key={choice.id}>
            <input type="radio" name={question.id} value={choice.id} checked={answer === choice.id} onChange={(e) => setAnswer(e.target.value)} />
            {choice.text}
          </label>
        ))}

      {question.question_type === "true_false" &&
        ["true", "false"].map((value) => (
          <label key={value}>
            <input type="radio" name={question.id} value={value} checked={answer === value} onChange={(e) => setAnswer(e.target.value)} />
            {value === "true" ? "True" : "False"}
          </label>
        ))}

      {question.question_type === "text_input" && (
        <input type="text" aria-label="Your answer" value={answer} onChange={(e) => setAnswer(e.target.value)} />
      )}

      <button type="button" disabled={!answer.trim() || submitting} onClick={() => onSubmit(answer)}>
        {submitting ? "Checking…" : "Submit answer"}
      </button>
    </fieldset>
  );
}
