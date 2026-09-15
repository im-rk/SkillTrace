"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api-client";
import {
  questionBankApi,
  type Difficulty,
  type QuestionContent,
  type QuestionType,
} from "@/features/question-bank-admin/api/question-bank.api";
import type { Skill } from "@/features/question-bank-admin/api/skills.api";

function emptyContentFor(type: QuestionType): QuestionContent {
  switch (type) {
    case "multiple_choice":
      return { choices: [{ id: "a", text: "" }, { id: "b", text: "" }], correct_choice_id: "a" };
    case "true_false":
      return { correct_answer: true };
    case "text_input":
      return { correct_answer: "", case_sensitive: false };
  }
}

export function QuestionForm({ skills, onCreated }: { skills: Skill[]; onCreated: () => void }) {
  const [skillId, setSkillId] = useState(skills[0]?.id ?? "");
  const [questionType, setQuestionType] = useState<QuestionType>("multiple_choice");
  const [prompt, setPrompt] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("easy");
  const [content, setContent] = useState<QuestionContent>(() => emptyContentFor("multiple_choice"));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function changeType(type: QuestionType) {
    setQuestionType(type);
    setContent(emptyContentFor(type));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await questionBankApi.create({ skill_id: skillId, question_type: questionType, prompt, difficulty, content, tags: [] });
      setPrompt("");
      setContent(emptyContentFor(questionType));
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not create the question.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Skill
        <select value={skillId} onChange={(e) => setSkillId(e.target.value)} required>
          {skills.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Question type
        <select value={questionType} onChange={(e) => changeType(e.target.value as QuestionType)}>
          <option value="multiple_choice">Multiple choice</option>
          <option value="true_false">True / False</option>
          <option value="text_input">Text input</option>
        </select>
      </label>

      <label>
        Difficulty
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)}>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
      </label>

      <label>
        Prompt
        <textarea required value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      </label>

      {questionType === "multiple_choice" && "choices" in content && (
        <MCQFields content={content} onChange={setContent} />
      )}
      {questionType === "true_false" && "correct_answer" in content && typeof content.correct_answer === "boolean" && (
        <TrueFalseFields content={content} onChange={setContent} />
      )}
      {questionType === "text_input" && "correct_answer" in content && typeof content.correct_answer === "string" && (
        <TextInputFields content={content} onChange={setContent} />
      )}

      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={submitting || !skillId}>
        {submitting ? "Creating…" : "Create question"}
      </button>
    </form>
  );
}

function MCQFields({
  content,
  onChange,
}: {
  content: Extract<QuestionContent, { choices: unknown }>;
  onChange: (content: QuestionContent) => void;
}) {
  function updateChoiceText(id: string, text: string) {
    onChange({ ...content, choices: content.choices.map((c) => (c.id === id ? { ...c, text } : c)) });
  }
  function addChoice() {
    const nextId = String.fromCharCode(97 + content.choices.length); // a, b, c, ...
    onChange({ ...content, choices: [...content.choices, { id: nextId, text: "" }] });
  }

  return (
    <fieldset>
      <legend>Choices</legend>
      {content.choices.map((choice) => (
        <label key={choice.id}>
          <input
            type="radio"
            name="correct_choice"
            checked={content.correct_choice_id === choice.id}
            onChange={() => onChange({ ...content, correct_choice_id: choice.id })}
          />
          <input
            required
            value={choice.text}
            onChange={(e) => updateChoiceText(choice.id, e.target.value)}
            placeholder={`Choice ${choice.id}`}
          />
        </label>
      ))}
      <button type="button" onClick={addChoice}>
        Add choice
      </button>
    </fieldset>
  );
}

function TrueFalseFields({
  content,
  onChange,
}: {
  content: Extract<QuestionContent, { correct_answer: boolean }>;
  onChange: (content: QuestionContent) => void;
}) {
  return (
    <label>
      Correct answer
      <select
        value={String(content.correct_answer)}
        onChange={(e) => onChange({ ...content, correct_answer: e.target.value === "true" })}
      >
        <option value="true">True</option>
        <option value="false">False</option>
      </select>
    </label>
  );
}

function TextInputFields({
  content,
  onChange,
}: {
  content: Extract<QuestionContent, { correct_answer: string }>;
  onChange: (content: QuestionContent) => void;
}) {
  return (
    <>
      <label>
        Correct answer
        <input required value={content.correct_answer} onChange={(e) => onChange({ ...content, correct_answer: e.target.value })} />
      </label>
      <label>
        <input
          type="checkbox"
          checked={content.case_sensitive}
          onChange={(e) => onChange({ ...content, case_sensitive: e.target.checked })}
        />
        Case sensitive
      </label>
    </>
  );
}
