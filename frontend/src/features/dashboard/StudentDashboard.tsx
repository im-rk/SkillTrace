"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { MyExams } from "@/features/enrollment/components/MyExams";
import { RedeemCodeForm } from "@/features/enrollment/components/RedeemCodeForm";
import { SkillProgressCard } from "@/features/practice/components/SkillProgressCard";
import { practiceApi, type SkillMastery } from "@/features/practice/api/practice.api";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, LoadingBlock, Notice } from "@/components/ui/Bits";
import { greeting } from "@/lib/format";

export function StudentDashboard() {
  const { user } = useAuth();
  const router = useRouter();
  const [skills, setSkills] = useState<SkillMastery[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    practiceApi
      .mySkills(user.user_id)
      .then((rows) => !cancelled && setSkills(rows))
      .catch(() => !cancelled && setSkills([]));
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function start(skillId: string) {
    setStarting(true);
    setError(null);
    try {
      const session = await practiceApi.start(skillId);
      router.push(`/quiz/${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not start practice.");
      setStarting(false);
    }
  }

  const firstName = user?.display_name.split(" ")[0] ?? "";
  // Practice what is in progress first, then what has not been started, mastered skills last.
  const ordered = [...(skills ?? [])]
    .filter((s) => s.question_count > 0) // a skill with no questions has nothing to practise yet
    .sort((a, b) => Number(a.is_mastered) - Number(b.is_mastered) || b.total_attempts - a.total_attempts);

  return (
    <main>
      <PageHeader eyebrow="Dashboard" title={`${greeting()}, ${firstName}`} lede="Practice to build mastery, and take the exams your instructor opens for you." />

      <div className="split">
        <section className="card" aria-labelledby="my-exams-title">
          <div className="card-head">
            <h2 className="h2" id="my-exams-title">
              My exams
            </h2>
          </div>
          <MyExams />
        </section>

        <section className="card card-pad" aria-labelledby="join-title">
          <h2 className="h2" id="join-title" style={{ marginBottom: 4 }}>
            Have an access code?
          </h2>
          <p className="muted small" style={{ marginBottom: 16 }}>
            Enter it to add the exam to your dashboard.
          </p>
          <RedeemCodeForm compact />
        </section>
      </div>

      <div className="row-between" style={{ margin: "40px 0 16px" }}>
        <div>
          <h2 className="h2">Your skills</h2>
          <p className="muted small">The system adapts the questions to what you already know.</p>
        </div>
        <Link href="/progress" className="link small">
          See all progress
        </Link>
      </div>

      {error && <Notice tone="error">{error}</Notice>}
      {skills === null ? (
        <LoadingBlock lines={4} />
      ) : ordered.length === 0 ? (
        <div className="card">
          <EmptyState icon="book" title="No skills to practise yet">
            Your instructor has not published any skills with questions.
          </EmptyState>
        </div>
      ) : (
        <div className="grid grid-auto">
          {ordered.map((skill) => (
            <SkillProgressCard key={skill.skill_id} skill={skill} onStart={start} starting={starting} />
          ))}
        </div>
      )}
    </main>
  );
}
