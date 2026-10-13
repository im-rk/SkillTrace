"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api-client";
import { questionBankApi, type Difficulty, type QuestionCreate } from "@/features/question-bank-admin/api/question-bank.api";
import { answerText } from "@/features/question-bank-admin/components/QuestionList";
import { DifficultyChip, Chip, typeLabel } from "@/components/ui/Chip";
import { Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";

const LEVELS: { id: Difficulty | "mixed"; label: string }[] = [
  { id: "mixed", label: "Mixed" },
  { id: "easy", label: "Easy" },
  { id: "medium", label: "Medium" },
  { id: "hard", label: "Hard" },
];

/** Asks an LLM for draft questions. Nothing is saved until the instructor ticks the ones they trust. */
export function AiDraftPanel({ skillId, onSaved, onClose }: { skillId: string; onSaved: () => void; onClose: () => void }) {
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState<Difficulty | "mixed">("mixed");
  const [topic, setTopic] = useState("");
  const [drafts, setDrafts] = useState<QuestionCreate[]>([]);
  const [picked, setPicked] = useState<boolean[]>([]);
  const [discarded, setDiscarded] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  async function generate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setGenerating(true);
    try {
      const res = await questionBankApi.generate({ skill_id: skillId, count, difficulty, topic: topic.trim() || undefined });
      setDrafts(res.drafts);
      setPicked(res.drafts.map(() => true));
      setDiscarded(res.discarded);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not generate questions.");
    } finally {
      setGenerating(false);
    }
  }

  async function saveSelected() {
    setError(null);
    setSaving(true);
    try {
      const chosen = drafts.filter((_, i) => picked[i]);
      for (const draft of chosen) await questionBankApi.create(draft);
      setMessage(`Saved ${chosen.length} question${chosen.length === 1 ? "" : "s"} to the question bank.`);
      setDrafts([]);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not save the questions.");
    } finally {
      setSaving(false);
    }
  }

  const pickedCount = picked.filter(Boolean).length;

  return (
    <section className="card" aria-label="Draft questions with AI">
      <div className="card-head">
        <div>
          <h2 className="h2">Draft questions with AI</h2>
          <p className="muted small">The AI writes drafts; you review them and keep only the ones you trust.</p>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close AI drafting">
          <Icon name="x" />
        </button>
      </div>
      <div className="card-body stack">
        <form onSubmit={generate} className="form-grid">
          <div className="field">
            <label htmlFor="ai-count">How many questions</label>
            <select id="ai-count" className="select" value={count} onChange={(e) => setCount(Number(e.target.value))}>
              {[3, 5, 8, 10].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="label" id="ai-level">
              Difficulty
            </span>
            <div className="segmented" role="radiogroup" aria-labelledby="ai-level">
              {LEVELS.map((l) => (
                <button key={l.id} type="button" role="radio" aria-checked={difficulty === l.id} onClick={() => setDifficulty(l.id)}>
                  {l.label}
                </button>
              ))}
            </div>
          </div>
          <div className="field full">
            <label htmlFor="ai-topic">Focus (optional)</label>
            <input id="ai-topic" className="input" maxLength={200} value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. adding fractions with unlike denominators" />
          </div>
          <div className="full">
            <button type="submit" className="btn btn-primary" disabled={generating}>
              <Icon name="pencil" small />
              {generating ? "Drafting…" : "Draft questions"}
            </button>
          </div>
        </form>

        {error && (
          <Notice tone={error.includes("not configured") ? "info" : "error"}>
            {error.includes("not configured") ? (
              <>AI drafting is not switched on for this server. An administrator can enable it by setting a GROQ_API_KEY.</>
            ) : (
              error
            )}
          </Notice>
        )}
        {message && <Notice tone="ok" role="status">{message}</Notice>}

        {drafts.length > 0 && (
          <div data-testid="ai-drafts" className="stack-sm">
            <Notice tone="warn">
              AI can be wrong. Check each answer before you keep a question.
              {discarded > 0 && ` ${discarded} invalid draft${discarded === 1 ? " was" : "s were"} thrown away.`}
            </Notice>
            {drafts.map((d, i) => (
              <label key={i} className="draft" data-picked={picked[i]}>
                <input
                  type="checkbox"
                  className="check"
                  checked={picked[i] ?? false}
                  aria-label={d.prompt}
                  onChange={(e) => setPicked(picked.map((p, j) => (j === i ? e.target.checked : p)))}
                />
                <div>
                  <div style={{ fontWeight: 580 }}>{d.prompt}</div>
                  <div className="q-meta">
                    <DifficultyChip difficulty={d.difficulty} />
                    <Chip dot={false}>{typeLabel(d.question_type)}</Chip>
                    <span className="muted small">
                      Answer: <b style={{ color: "var(--ink-2)" }}>{answerText(d.content)}</b>
                    </span>
                  </div>
                  {"choices" in d.content && (
                    <ul className="muted small" style={{ margin: "8px 0 0 18px" }}>
                      {d.content.choices.map((c) => (
                        <li key={c.id}>{c.text}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </label>
            ))}
            <div className="row">
              <button type="button" className="btn btn-primary" onClick={saveSelected} disabled={saving || pickedCount === 0}>
                Save selected
              </button>
              <span className="muted small num">{pickedCount} of {drafts.length} selected</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
