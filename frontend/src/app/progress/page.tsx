"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { practiceApi, type Progress } from "@/features/practice/api/practice.api";
import { ChartKey, ProgressChart } from "@/features/practice/components/ProgressChart";
import { PageHeader } from "@/components/ui/PageHeader";
import { Chip } from "@/components/ui/Chip";
import { EmptyState, LoadingBlock, Notice, Stat } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";
import { pct } from "@/lib/format";

function AnswerTable({ progress }: { progress: Progress }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="sr-only">Mastery after each answer</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Where</th>
            <th scope="col">Result</th>
            <th scope="col">Mastery</th>
            <th scope="col" className="right">
              Change
            </th>
          </tr>
        </thead>
        <tbody>
          {progress.points.map((p, i) => {
            const change = pct(p.mastery_after) - pct(p.mastery_before);
            return (
              <tr key={i}>
                <td className="num">{i + 1}</td>
                <td>{p.source === "exam" ? "Exam" : "Practice"}</td>
                <td>{p.is_correct ? <Chip tone="ok">Correct</Chip> : <Chip tone="bad">Incorrect</Chip>}</td>
                <td className="num">
                  {pct(p.mastery_before)}% → {pct(p.mastery_after)}%
                </td>
                <td className="right num">
                  <span className={`delta ${change >= 0 ? "up" : "down"}`}>
                    {change >= 0 ? "+" : "−"}
                    {Math.abs(change)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ProgressContent({ studentId }: { studentId: string }) {
  const initialSkill = useSearchParams().get("skill") ?? "";
  const [skills, setSkills] = useState<{ id: string; name: string }[]>([]);
  const [skillId, setSkillId] = useState(initialSkill);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Only skills with questions, the ones the student has practised first, so the page opens on something with data.
    practiceApi.mySkills(studentId).then((rows) => {
      if (cancelled) return;
      const usable = rows.filter((s) => s.question_count > 0).sort((a, b) => b.total_attempts - a.total_attempts);
      setSkills(usable.map((s) => ({ id: s.skill_id, name: s.name })));
      setSkillId((current) => current || usable[0]?.skill_id || "");
    });
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  useEffect(() => {
    if (!skillId) return;
    let cancelled = false;
    practiceApi
      .progress(studentId, skillId)
      .then((p) => {
        if (cancelled) return;
        setError(null);
        setProgress(p);
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.detail : "Could not load progress."));
    return () => {
      cancelled = true;
    };
  }, [studentId, skillId]);

  const ready = progress && progress.skill_id === skillId;
  const viterbiAt = ready ? progress.points.findIndex((p) => p.viterbi_mastered) + 1 : 0;
  const examAnswers = ready ? progress.points.filter((p) => p.source === "exam").length : 0;
  const mastered = ready && progress.current_mastery !== null && progress.current_mastery >= progress.mastery_threshold;

  return (
    <main>
      <PageHeader
        eyebrow="Progress"
        title="How your mastery has moved"
        lede="Every answer, in practice or in an exam, updates one estimate per skill. This is that estimate over time."
        actions={
          <div className="field" style={{ minWidth: 220 }}>
            <label htmlFor="skill-select" className="sr-only">
              Skill
            </label>
            <select id="skill-select" className="select" aria-label="Skill" value={skillId} onChange={(e) => setSkillId(e.target.value)}>
              {skills.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        }
      />

      {error && <Notice tone="error">{error}</Notice>}
      {!ready && !error && <LoadingBlock lines={5} />}

      {ready && progress.points.length === 0 && (
        <div className="card">
          <EmptyState
            icon="trend"
            title="No answers yet for this skill"
            action={
              <Link href="/practice" className="btn btn-primary">
                Start practising
              </Link>
            }
          >
            Answer a few questions and your mastery curve will appear here.
          </EmptyState>
        </div>
      )}

      {ready && progress.points.length > 0 && (
        <div className="stack">
          <div className="grid grid-4">
            <Stat label="Mastery now" value={progress.current_mastery === null ? "—" : `${pct(progress.current_mastery)}%`} sub={mastered ? "Goal reached" : `${Math.max(0, pct(progress.mastery_threshold) - pct(progress.current_mastery ?? 0))} points to go`} />
            <Stat label="Goal" value={`${pct(progress.mastery_threshold)}%`} sub="Mastered at or above this" />
            <Stat label="Answers" value={progress.points.length} sub={`${examAnswers} in exams`} />
            <Stat label="Status" value={mastered ? "Mastered" : "Learning"} sub={viterbiAt > 0 ? `Likely learned around answer ${viterbiAt}` : "Keep practising"} />
          </div>

          <section className="card" aria-label="Mastery over time">
            <div className="card-head">
              <h2 className="h2">{progress.skill_name}</h2>
              <p className="muted small num" data-testid="progress-summary">
                {progress.points.length} answers ({examAnswers} in exams). Current mastery {progress.current_mastery === null ? "—" : `${pct(progress.current_mastery)}%`}, goal {pct(progress.mastery_threshold)}%.
              </p>
            </div>
            <div className="card-body" style={{ paddingBottom: 12 }}>
              <ProgressChart progress={progress} />
              <div style={{ marginTop: 12 }}>
                <ChartKey />
              </div>
            </div>
            <div className="card-foot">
              <details className="disclosure">
                <summary>
                  <Icon name="list" small />
                  Show answer-by-answer table
                </summary>
                <AnswerTable progress={progress} />
              </details>
            </div>
          </section>

          <Notice tone="info">
            <b>Reading the chart.</b> The line is the system&apos;s running estimate that you know the skill. A correct answer lifts it, a wrong one lowers it, and
            neither can move it to 0% or 100%, because answers can be lucky guesses or careless slips. The vertical line marks when, looking at your whole history, you most likely learned the skill.
          </Notice>
        </div>
      )}
    </main>
  );
}

export default function ProgressPage() {
  const { user } = useAuth();
  return (
    <RequireAuth>
      <Suspense fallback={<main><LoadingBlock lines={4} /></main>}>{user && <ProgressContent studentId={user.user_id} />}</Suspense>
    </RequireAuth>
  );
}
