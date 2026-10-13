"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { practiceApi, type SkillMastery } from "@/features/practice/api/practice.api";
import { SkillProgressCard } from "@/features/practice/components/SkillProgressCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, LoadingBlock, Notice } from "@/components/ui/Bits";

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

  const visible = (skills ?? []).filter((s) => s.question_count > 0); // nothing to practise in an empty skill

  return (
    <main>
      <PageHeader
        eyebrow="Practice"
        title="Pick a skill to practise"
        lede="Each answer updates an estimate of how well you know the skill. Easier questions come first; harder ones follow as your estimate rises, until you reach the goal."
      />
      {error && <Notice tone="error">{error}</Notice>}
      {skills === null && !error && <LoadingBlock lines={4} />}
      {skills && visible.length === 0 && (
        <div className="card">
          <EmptyState icon="book" title="No skills are available yet">
            Your instructor has not added any skills with questions.
          </EmptyState>
        </div>
      )}
      <div className="grid grid-auto">
        {visible.map((skill) => (
          <SkillProgressCard key={skill.skill_id} skill={skill} onStart={start} starting={starting !== null} />
        ))}
      </div>
    </main>
  );
}

export default function PracticePage() {
  const { user } = useAuth();
  return <RequireAuth>{user && <PracticeContent studentId={user.user_id} />}</RequireAuth>;
}
