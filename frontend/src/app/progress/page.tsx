"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { skillsApi, type Skill } from "@/features/question-bank-admin/api/skills.api";
import { practiceApi, pct, type Progress } from "@/features/practice/api/practice.api";
import { ProgressChart } from "@/features/practice/components/ProgressChart";

function ProgressContent({ studentId }: { studentId: string }) {
  const initialSkill = useSearchParams().get("skill") ?? "";
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillId, setSkillId] = useState(initialSkill);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    skillsApi.list().then((rows) => {
      if (cancelled) return;
      setSkills(rows);
      setSkillId((current) => current || rows[0]?.id || "");
    });
    return () => {
      cancelled = true;
    };
  }, []);

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

  return (
    <main>
      <h1>My progress</h1>
      <label>
        Skill
        <select value={skillId} onChange={(e) => setSkillId(e.target.value)}>
          {skills.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      {progress && progress.skill_id === skillId && (
        <section>
          {progress.points.length === 0 ? (
            <p>
              No answers yet for this skill — <Link href="/practice">start practising</Link>.
            </p>
          ) : (
            <>
              <p data-testid="progress-summary">
                {progress.points.length} answers ({progress.points.filter((p) => p.source === "exam").length} in exams). Current mastery{" "}
                {progress.current_mastery === null ? "—" : `${pct(progress.current_mastery)}%`}, goal {pct(progress.mastery_threshold)}%.
              </p>
              <ProgressChart progress={progress} />
            </>
          )}
        </section>
      )}
      <p>
        <Link href="/dashboard">Back to dashboard</Link>
      </p>
    </main>
  );
}

export default function ProgressPage() {
  const { user } = useAuth();
  return (
    <RequireAuth>
      <Suspense fallback={<p>Loading…</p>}>{user && <ProgressContent studentId={user.user_id} />}</Suspense>
    </RequireAuth>
  );
}
