"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { skillsApi, type Skill } from "@/features/question-bank-admin/api/skills.api";
import { updateMastery } from "@/lib/bkt";
import { pct } from "@/lib/format";
import { Notice } from "@/components/ui/Bits";

const DEFAULTS = { p_l0: 0.3, p_t: 0.15, p_g: 0.2, p_s: 0.1, mastery_threshold: 0.85 };

const PARAMS = [
  {
    key: "p_l0",
    label: "Initial knowledge P(L0)",
    help: "How likely a student is to already know this skill before any practice. It is where every student's mastery starts.",
  },
  {
    key: "p_t",
    label: "Learning rate P(T)",
    help: "The chance a student learns the skill from one more practice question. Higher means mastery rises faster.",
  },
  {
    key: "p_g",
    label: "Guess P(G)",
    help: "The chance of answering correctly without knowing the skill. For true/false questions this is around 0.5; for four-option multiple choice around 0.25.",
  },
  {
    key: "p_s",
    label: "Slip P(S)",
    help: "The chance a student who does know the skill still gets it wrong, through carelessness.",
  },
  {
    key: "mastery_threshold",
    label: "Mastery threshold",
    help: "The mastery level at which the skill counts as learned and practice stops. Raise it to demand more evidence.",
  },
] as const;

type Key = (typeof PARAMS)[number]["key"];

/** The learning-model settings of one skill, with a live preview of what the numbers imply. */
export function BktSettings({ skill, onChanged }: { skill: Skill; onChanged: () => void }) {
  const router = useRouter();
  const [name, setName] = useState(skill.name);
  const [description, setDescription] = useState(skill.description ?? "");
  const [values, setValues] = useState<Record<Key, string>>(() => Object.fromEntries(PARAMS.map(({ key }) => [key, String(skill[key])])) as Record<Key, string>);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const preview = useMemo(() => {
    const n = (k: Key) => Math.min(1, Math.max(0, Number(values[k]) || 0));
    const params = { p_l0: n("p_l0"), p_t: n("p_t"), p_g: n("p_g"), p_s: n("p_s") };
    const threshold = n("mastery_threshold");
    const correct = updateMastery(params.p_l0, true, params);
    const wrong = updateMastery(params.p_l0, false, params);
    let m = params.p_l0;
    let needed: number | null = null;
    for (let i = 1; i <= 30; i++) {
      m = updateMastery(m, true, params);
      if (m >= threshold) {
        needed = i;
        break;
      }
    }
    return { start: params.p_l0, correct, wrong, needed, threshold };
  }, [values]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setSaving(true);
    try {
      await skillsApi.update(skill.id, {
        name: name.trim(),
        description: description.trim() || null,
        ...Object.fromEntries(PARAMS.map(({ key }) => [key, Number(values[key])])),
      });
      setMessage("Skill saved.");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not save this skill.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${skill.name}"? Existing questions, exams and history are kept.`)) return;
    try {
      await skillsApi.remove(skill.id);
      router.push("/admin/skills");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not delete this skill.");
    }
  }

  return (
    <div className="split">
      <form onSubmit={save} className="card card-pad stack">
        <div className="form-grid">
          <div className="field">
            <label htmlFor="s-name">Name</label>
            <input id="s-name" className="input" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="s-description">Description</label>
            <input id="s-description" className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
        </div>

        <div>
          <h2 className="h2">Learning model</h2>
          <p className="muted small" style={{ marginTop: 4 }}>
            These five numbers tell the model how to read a student&apos;s answers. The defaults are the standard textbook values and work well to start with.
          </p>
        </div>

        <div className="stack-sm">
          {PARAMS.map(({ key, label, help }) => (
            <div key={key} className="field">
              <div className="row-between">
                <label htmlFor={`p-${key}`}>{label}</label>
                <input
                  id={`p-${key}`}
                  className="input num"
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  required
                  value={values[key]}
                  onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                  style={{ width: 96 }}
                />
              </div>
              <span className="hint">{help}</span>
            </div>
          ))}
        </div>

        {error && <Notice tone="error">{error}</Notice>}
        {message && <Notice tone="ok" role="status">{message}</Notice>}

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Save skill"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setValues(Object.fromEntries(PARAMS.map(({ key }) => [key, String(DEFAULTS[key])])) as Record<Key, string>)}
          >
            Reset to defaults
          </button>
          <span style={{ flex: 1 }} />
          <button type="button" className="btn btn-danger" onClick={remove}>
            Delete skill
          </button>
        </div>
      </form>

      <aside className="card card-pad" aria-label="What these settings mean" style={{ position: "sticky", top: 80 }}>
        <h2 className="h2">What these numbers do</h2>
        <p className="muted small" style={{ margin: "4px 0 16px" }}>
          Live preview for a new student, using the values on the left.
        </p>
        <dl className="stack-sm" style={{ margin: 0 }}>
          <div className="row-between">
            <dt className="muted">Starts at</dt>
            <dd className="num" style={{ fontWeight: 650 }}>
              {pct(preview.start)}%
            </dd>
          </div>
          <div className="row-between">
            <dt className="muted">After one correct answer</dt>
            <dd className="num" style={{ fontWeight: 650, color: "var(--ok)" }}>
              {pct(preview.correct)}%
            </dd>
          </div>
          <div className="row-between">
            <dt className="muted">After one wrong answer</dt>
            <dd className="num" style={{ fontWeight: 650, color: "var(--rust)" }}>
              {pct(preview.wrong)}%
            </dd>
          </div>
          <div className="row-between">
            <dt className="muted">Correct answers in a row to master</dt>
            <dd className="num" style={{ fontWeight: 650 }}>
              {preview.needed ?? "30+"}
            </dd>
          </div>
        </dl>
        {preview.needed !== null && preview.needed <= 2 && (
          <div style={{ marginTop: 16 }}>
            <Notice tone="warn">
              This skill is mastered after only {preview.needed} correct {preview.needed === 1 ? "answer" : "answers"}. Raise the threshold or lower the learning rate and guess chance for a stricter measure.
            </Notice>
          </div>
        )}
      </aside>
    </div>
  );
}
