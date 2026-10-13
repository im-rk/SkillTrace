"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api-client";
import { questionBankApi, type Difficulty, type QuestionContent, type QuestionType } from "@/features/question-bank-admin/api/question-bank.api";
import { Modal } from "@/components/ui/Modal";
import { Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";

const TYPES: { id: QuestionType; label: string }[] = [
  { id: "multiple_choice", label: "Multiple choice" },
  { id: "true_false", label: "True / false" },
  { id: "text_input", label: "Short answer" },
];

const LEVELS: { id: Difficulty; label: string; hint: string }[] = [
  { id: "easy", label: "Easy", hint: "Asked when a student is just starting" },
  { id: "medium", label: "Medium", hint: "Asked once they are partway there" },
  { id: "hard", label: "Hard", hint: "Used to confirm mastery" },
];

const LETTERS = "ABCDEF";
const MIN_OPTIONS = 2;
const MAX_OPTIONS = 6;

interface Option {
  text: string;
}

/** Add one question to a skill. The multiple-choice builder starts with four empty options, because four is the usual shape. */
export function QuestionEditor({ skillId, open, onClose, onSaved }: { skillId: string; open: boolean; onClose: () => void; onSaved: () => void }) {
  const [type, setType] = useState<QuestionType>("multiple_choice");
  const [difficulty, setDifficulty] = useState<Difficulty>("easy");
  const [prompt, setPrompt] = useState("");
  const [options, setOptions] = useState<Option[]>([{ text: "" }, { text: "" }, { text: "" }, { text: "" }]);
  const [correctIndex, setCorrectIndex] = useState<number | null>(null);
  const [trueFalse, setTrueFalse] = useState(true);
  const [shortAnswer, setShortAnswer] = useState("");
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const optionsFilled = options.every((o) => o.text.trim());
  const valid =
    prompt.trim().length > 0 &&
    (type === "multiple_choice" ? optionsFilled && correctIndex !== null : type === "text_input" ? shortAnswer.trim().length > 0 : true);

  function setOptionText(index: number, text: string) {
    setOptions((current) => current.map((o, i) => (i === index ? { text } : o)));
  }

  function removeOption(index: number) {
    setOptions((current) => current.filter((_, i) => i !== index));
    setCorrectIndex((current) => (current === null ? null : current === index ? null : current > index ? current - 1 : current));
  }

  function buildContent(): QuestionContent {
    if (type === "multiple_choice") {
      const choices = options.map((o, i) => ({ id: String.fromCharCode(97 + i), text: o.text.trim() }));
      return { choices, correct_choice_id: choices[correctIndex ?? 0].id };
    }
    if (type === "true_false") return { correct_answer: trueFalse };
    return { correct_answer: shortAnswer.trim(), case_sensitive: caseSensitive };
  }

  function reset() {
    setPrompt("");
    setOptions([{ text: "" }, { text: "" }, { text: "" }, { text: "" }]);
    setCorrectIndex(null);
    setShortAnswer("");
    setError(null);
  }

  async function handleSubmit(e: FormEvent, addAnother: boolean) {
    e.preventDefault();
    if (!valid) return;
    setError(null);
    setSaving(true);
    try {
      await questionBankApi.create({ skill_id: skillId, question_type: type, prompt: prompt.trim(), difficulty, content: buildContent(), tags: [] });
      onSaved();
      reset();
      if (!addAnother) onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not save the question.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a question"
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-secondary" disabled={!valid || saving} onClick={(e) => handleSubmit(e, true)}>
            Save and add another
          </button>
          <button type="submit" form="question-form" className="btn btn-primary" disabled={!valid || saving}>
            {saving ? "Saving…" : "Save question"}
          </button>
        </>
      }
    >
      <form id="question-form" onSubmit={(e) => handleSubmit(e, false)} className="stack">
        <div className="stack-sm">
          <div className="field">
            <span className="label" id="type-label">
              Question type
            </span>
            <div className="segmented" role="radiogroup" aria-labelledby="type-label">
              {TYPES.map((t) => (
                <button key={t.id} type="button" role="radio" aria-checked={type === t.id} onClick={() => setType(t.id)}>
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <span className="label" id="level-label">
              Difficulty
            </span>
            <div className="segmented" role="radiogroup" aria-labelledby="level-label">
              {LEVELS.map((l) => (
                <button key={l.id} type="button" role="radio" aria-checked={difficulty === l.id} onClick={() => setDifficulty(l.id)} title={l.hint}>
                  {l.label}
                </button>
              ))}
            </div>
            <span className="hint">{LEVELS.find((l) => l.id === difficulty)?.hint}</span>
          </div>
        </div>

        <div className="field">
          <label htmlFor="q-prompt">Question</label>
          <textarea id="q-prompt" className="textarea" required autoFocus value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="What is 3/4 + 1/8?" />
        </div>

        {type === "multiple_choice" && (
          <div className="field">
            <span className="label">Answer options</span>
            <span className="hint">Type each option, then mark the one correct answer.</span>
            <div className="stack-sm" style={{ marginTop: 6 }}>
              {options.map((option, index) => (
                <div key={index} className="option-row">
                  <span className="option-letter" aria-hidden="true">
                    {LETTERS[index]}
                  </span>
                  <input
                    className="input"
                    aria-label={`Option ${LETTERS[index]}`}
                    value={option.text}
                    onChange={(e) => setOptionText(index, e.target.value)}
                    placeholder={`Option ${LETTERS[index]}`}
                  />
                  <button
                    type="button"
                    className="correct-toggle"
                    aria-pressed={correctIndex === index}
                    aria-label={`Mark option ${LETTERS[index]} as correct`}
                    onClick={() => setCorrectIndex(index)}
                  >
                    <Icon name="check" small />
                    {correctIndex === index ? "Correct" : "Mark correct"}
                  </button>
                  {options.length > MIN_OPTIONS ? (
                    <button type="button" className="btn btn-ghost btn-sm remove" aria-label={`Remove option ${LETTERS[index]}`} onClick={() => removeOption(index)}>
                      <Icon name="x" small />
                    </button>
                  ) : (
                    <span />
                  )}
                </div>
              ))}
            </div>
            {options.length < MAX_OPTIONS && (
              <div>
                <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 6 }} onClick={() => setOptions((o) => [...o, { text: "" }])}>
                  <Icon name="plus" small />
                  Add option
                </button>
              </div>
            )}
          </div>
        )}

        {type === "true_false" && (
          <div className="field">
            <span className="label" id="tf-label">
              The statement is
            </span>
            <div className="segmented" role="radiogroup" aria-labelledby="tf-label">
              <button type="button" role="radio" aria-checked={trueFalse} onClick={() => setTrueFalse(true)}>
                True
              </button>
              <button type="button" role="radio" aria-checked={!trueFalse} onClick={() => setTrueFalse(false)}>
                False
              </button>
            </div>
            <span className="hint">Write the question as a statement students judge, for example &ldquo;1/2 is equal to 2/4.&rdquo;</span>
          </div>
        )}

        {type === "text_input" && (
          <div className="stack-sm">
            <div className="field">
              <label htmlFor="q-answer">Correct answer</label>
              <input id="q-answer" className="input" value={shortAnswer} onChange={(e) => setShortAnswer(e.target.value)} placeholder="e.g. 7/8" />
              <span className="hint">Keep it to one short, unambiguous form. Spacing and trailing punctuation are ignored when checking.</span>
            </div>
            <label className="row" style={{ gap: 10, fontWeight: 500 }}>
              <input type="checkbox" className="check" checked={caseSensitive} onChange={(e) => setCaseSensitive(e.target.checked)} />
              Capitalisation must match
            </label>
          </div>
        )}

        {error && <Notice tone="error">{error}</Notice>}
      </form>
    </Modal>
  );
}
