"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api-client";
import { examAdminApi, type AssignedQuestion } from "@/features/exam-admin/api/exam-admin.api";
import { questionBankApi, type Question } from "@/features/question-bank-admin/api/question-bank.api";
import { DifficultyChip, typeLabel, Chip } from "@/components/ui/Chip";
import { EmptyState, LoadingBlock, Notice } from "@/components/ui/Bits";
import { plural } from "@/lib/format";

/** Chooses which of the skill's questions go into the exam, and how many points each is worth.
 * Saving replaces the exam's question set, until the first student starts. */
export function QuestionPicker({
  examId,
  skillId,
  skillName,
  readOnly,
  onSaved,
}: {
  examId: string;
  skillId: string;
  skillName: string;
  readOnly: boolean;
  onSaved: (count: number) => void;
}) {
  const [bank, setBank] = useState<Question[] | null>(null);
  const [order, setOrder] = useState<string[]>([]); // selected question ids, in the order students will see them
  const [points, setPoints] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([questionBankApi.list(skillId), examAdminApi.assignedQuestions(examId)]).then(([questions, assigned]) => {
      if (cancelled) return;
      setBank(questions);
      setOrder(assigned.map((a) => a.question_id));
      setPoints(Object.fromEntries(assigned.map((a) => [a.question_id, String(Number(a.points))])));
    });
    return () => {
      cancelled = true;
    };
  }, [examId, skillId]);

  function toggle(id: string) {
    setSaved(false);
    setOrder((current) => (current.includes(id) ? current.filter((q) => q !== id) : [...current, id]));
    setPoints((current) => ({ ...current, [id]: current[id] ?? "1" }));
  }

  function selectTier(tier: "easy" | "medium" | "hard" | "all", on: boolean) {
    setSaved(false);
    const ids = (bank ?? []).filter((q) => tier === "all" || q.difficulty === tier).map((q) => q.id);
    setOrder((current) => (on ? [...current, ...ids.filter((id) => !current.includes(id))] : current.filter((id) => !ids.includes(id))));
    setPoints((current) => ({ ...Object.fromEntries(ids.map((id) => [id, "1"])), ...current }));
  }

  async function save() {
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      const assignments: AssignedQuestion[] = order.map((questionId, index) => ({ question_id: questionId, display_order: index + 1, points: points[questionId] || "1" }));
      await examAdminApi.assignQuestions(examId, assignments);
      setSaved(true);
      onSaved(assignments.length);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not save the questions.");
    } finally {
      setSaving(false);
    }
  }

  if (bank === null) return <div className="card-body"><LoadingBlock lines={4} /></div>;
  if (bank.length === 0)
    return (
      <EmptyState
        icon="book"
        title={`${skillName} has no questions yet`}
        action={
          <Link href={`/admin/skills/${skillId}`} className="btn btn-primary">
            Add questions to {skillName}
          </Link>
        }
      >
        Exams use the questions in the skill&apos;s question bank.
      </EmptyState>
    );

  const totalPoints = order.reduce((sum, id) => sum + (Number(points[id]) || 0), 0);
  const tiers = (["easy", "medium", "hard"] as const).map((tier) => {
    const ids = bank.filter((q) => q.difficulty === tier).map((q) => q.id);
    return { tier, ids, allOn: ids.length > 0 && ids.every((id) => order.includes(id)) };
  });

  return (
    <div>
      {!readOnly && (
        <div className="card-head" style={{ flexWrap: "wrap" }}>
          <span className="muted small">Select the questions students will answer.</span>
          <div className="row">
            {tiers.map(({ tier, ids, allOn }) => (
              <button key={tier} type="button" className="btn btn-secondary btn-sm" disabled={ids.length === 0} onClick={() => selectTier(tier, !allOn)} style={{ textTransform: "capitalize" }}>
                {allOn ? "Clear" : "All"} {tier} ({ids.length})
              </button>
            ))}
          </div>
        </div>
      )}

      <ul className="divided" style={{ listStyle: "none" }}>
        {bank.map((q) => {
          const picked = order.includes(q.id);
          return (
            <li key={q.id} className="q-row" style={{ gridTemplateColumns: "auto minmax(0, 1fr) auto", alignItems: "start" }}>
              <input id={`pick-${q.id}`} aria-label={q.prompt} type="checkbox" className="check" style={{ marginTop: 4 }} checked={picked} disabled={readOnly} onChange={() => toggle(q.id)} />
              <label htmlFor={`pick-${q.id}`} style={{ cursor: readOnly ? "default" : "pointer", fontWeight: 400 }}>
                <span className="prompt" style={{ fontWeight: 560 }}>
                  {q.prompt}
                </span>
                <span className="q-meta" style={{ display: "flex" }}>
                  <DifficultyChip difficulty={q.difficulty} />
                  <Chip dot={false}>{typeLabel(q.question_type)}</Chip>
                  {picked && <span className="muted small num">Q{order.indexOf(q.id) + 1}</span>}
                </span>
              </label>
              {picked && (
                <label className="row" style={{ gap: 6, fontWeight: 400 }}>
                  <span className="muted small">Points</span>
                  <input
                    type="number"
                    className="input num"
                    step="0.5"
                    min="0"
                    disabled={readOnly}
                    value={points[q.id] ?? "1"}
                    onChange={(e) => {
                      setSaved(false);
                      setPoints((current) => ({ ...current, [q.id]: e.target.value }));
                    }}
                    aria-label={`Points for ${q.prompt}`}
                    style={{ width: 76, minHeight: 34, padding: "4px 8px" }}
                  />
                </label>
              )}
            </li>
          );
        })}
      </ul>

      {!readOnly && (
        <div className="card-foot">
          <div className="row-between">
            <span className="small num">
              <b>{plural(order.length, "question")}</b> selected · {totalPoints} {totalPoints === 1 ? "point" : "points"} in total
            </span>
            <button type="button" className="btn btn-primary" disabled={saving || order.length === 0} onClick={save}>
              {saving ? "Saving…" : "Save questions"}
            </button>
          </div>
          {error && (
            <div style={{ marginTop: 12 }}>
              <Notice tone="error">{error}</Notice>
            </div>
          )}
          {saved && (
            <div style={{ marginTop: 12 }}>
              <Notice tone="ok" role="status">
                Questions saved.
              </Notice>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
