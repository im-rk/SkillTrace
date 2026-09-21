"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { practiceApi, pct, type SkillMastery } from "@/features/practice/api/practice.api";

function PracticeContent({ studentId }: { studentId: string }) {
  const router = useRouter();
  const [skills, setSkills] = useState<SkillMastery[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    practiceApi
      .mySkills(studentId)
      .then((rows) => !cancelled && setSkills(rows))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.detail : "Could not load skills."));
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  async function start(skillId: string) {
    setStarting(skillId);
    setError(null);
    try {
      const session = await practiceApi.start(skillId);
      router.push(`/quiz/${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not start practice.");
      setStarting(null);
    }
  }

  return (
    <main>
      <h1>Practice</h1>
      <p>Pick a skill. Questions adapt to your current mastery until you reach the goal.</p>
      {error && <p role="alert">{error}</p>}
      {skills === null && !error && <p>Loading skills…</p>}
      {skills?.length === 0 && <p>No skills are available yet.</p>}
      <ul>
        {skills?.map((skill) => (
          <li key={skill.skill_id} data-testid="practice-skill">
            <strong>{skill.name}</strong>
            {skill.description && <> — {skill.description}</>}
            <br />
            <small>
              {skill.current_mastery === null
                ? "Not started"
                : `Mastery ${pct(skill.current_mastery)}% after ${skill.total_attempts} answers${skill.is_mastered ? " — mastered" : ""}`}
              {" · "}
              {skill.question_count} questions
            </small>
            <br />
            {skill.is_mastered ? (
              <strong>Mastered ✓ </strong>
            ) : (
              <button type="button" disabled={skill.question_count === 0 || starting !== null} onClick={() => start(skill.skill_id)}>
                {skill.total_attempts > 0 ? "Continue practice" : "Start practice"}
              </button>
            )}{" "}
            <Link href={`/progress?skill=${skill.skill_id}`}>Progress</Link>
          </li>
        ))}
      </ul>
      <p>
        <Link href="/dashboard">Back to dashboard</Link>
      </p>
    </main>
  );
}

export default function PracticePage() {
  const { user } = useAuth();
  return <RequireAuth>{user && <PracticeContent studentId={user.user_id} />}</RequireAuth>;
}
