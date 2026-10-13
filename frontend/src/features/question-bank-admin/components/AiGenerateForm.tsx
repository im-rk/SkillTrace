"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api-client";
import {
  questionBankApi,
  type Difficulty,
  type QuestionCreate,
} from "@/features/question-bank-admin/api/question-bank.api";
import type { Skill } from "@/features/question-bank-admin/api/skills.api";

function correctAnswerText(q: QuestionCreate): string {
  const c = q.content;
  if ("choices" in c) return c.choices.find((ch) => ch.id === c.correct_choice_id)?.text ?? "?";
  if ("case_sensitive" in c) return c.correct_answer;
  return c.correct_answer ? "True" : "False";
}

/** Asks the LLM for draft questions; nothing is saved until the instructor ticks and approves them. */
export function AiGenerateForm({ skills, onSaved }: { skills: Skill[]; onSaved: () => void }) {
  const [skillId, setSkillId] = useState(skills[0]?.id ?? "");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState<Difficulty | "mixed">("mixed");
  const [topic, setTopic] = useState("");
  const [drafts, setDrafts] = useState<QuestionCreate[]>([]);
  const [picked, setPicked] = useState<boolean[]>([]);
  const [discarded, setDiscarded] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function generate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      const res = await questionBankApi.generate({ skill_id: skillId, count, difficulty, topic: topic.trim() || undefined });
      setDrafts(res.drafts);
      setPicked(res.drafts.map(() => true));
      setDiscarded(res.discarded);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not generate questions.");
    } finally {
      setBusy(false);
    }
  }

  async function saveSelected() {
    setError(null);
    setBusy(true);
    try {
      const chosen = drafts.filter((_, i) => picked[i]);
      for (const draft of chosen) await questionBankApi.create(draft);
      setMessage(`Saved ${chosen.length} question${chosen.length === 1 ? "" : "s"} to the question bank.`);
      setDrafts([]);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not save the questions.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <form onSubmit={generate}>
        <label>
          Generate for skill
          <select value={skillId} onChange={(e) => setSkillId(e.target.value)}>
            {skills.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          How many (1–10)
          <input type="number" min={1} max={10} value={count} onChange={(e) => setCount(Number(e.target.value))} />
        </label>
        <label>
          AI difficulty
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty | "mixed")}>
            <option value="mixed">Mixed</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
        <label>
          Focus (optional)
          <input value={topic} maxLength={200} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. adding unlike denominators" />
        </label>
        <button type="submit" disabled={busy || !skillId}>
          {busy && drafts.length === 0 ? "Generating…" : "Generate with AI"}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}

      {drafts.length > 0 && (
        <div data-testid="ai-drafts">
          <p>
            Review the drafts — AI can be wrong. Only ticked questions are saved.
            {discarded > 0 && ` (${discarded} invalid draft${discarded === 1 ? "" : "s"} discarded.)`}
          </p>
          <ul>
            {drafts.map((d, i) => (
              <li key={i}>
                <label>
                  <input
                    type="checkbox"
                    checked={picked[i] ?? false}
                    onChange={(e) => setPicked(picked.map((p, j) => (j === i ? e.target.checked : p)))}
                  />
                  <strong>{d.prompt}</strong>
                </label>
                <div>
                  {d.difficulty} · {d.question_type.replace("_", " ")} · answer: {correctAnswerText(d)}
                </div>
              </li>
            ))}
          </ul>
          <button type="button" onClick={saveSelected} disabled={busy || !picked.some(Boolean)}>
            Save selected
          </button>
        </div>
      )}
    </div>
  );
}
