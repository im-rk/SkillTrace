"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { skillsApi, type Skill } from "@/features/question-bank-admin/api/skills.api";
import { SkillCard } from "@/features/question-bank-admin/components/SkillCard";
import { CreateSkillDialog } from "@/features/question-bank-admin/components/CreateSkillDialog";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, LoadingBlock, Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";

function SkillsContent() {
  const [skills, setSkills] = useState<Skill[] | null>(null);
  const [creating, setCreating] = useState(useSearchParams().get("new") === "1");

  useEffect(() => {
    let cancelled = false;
    skillsApi.list().then((rows) => !cancelled && setSkills(rows));
    return () => {
      cancelled = true;
    };
  }, []);

  const newSkillButton = (
    <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
      <Icon name="plus" small />
      New skill
    </button>
  );

  return (
    <main>
      <PageHeader
        eyebrow="Skills"
        title="Your skills"
        lede="A skill is a topic students should master. Each skill has its own question bank and its own learning model; exams are built from a skill's questions."
        actions={skills && skills.length > 0 ? newSkillButton : undefined}
      />

      {skills === null && <LoadingBlock lines={4} />}

      {skills?.length === 0 && (
        <div className="card">
          <EmptyState icon="book" title="Create your first skill" action={newSkillButton}>
            Start with the topic you want to teach, such as Fractions. You will add easy, medium and hard questions to it next.
          </EmptyState>
        </div>
      )}

      {skills && skills.length > 0 && (
        <>
          <div className="grid grid-auto">
            {skills.map((skill) => (
              <SkillCard key={skill.id} skill={skill} />
            ))}
          </div>
          <div style={{ marginTop: 24 }}>
            <Notice tone="info">
              A skill is <b>ready</b> once it has at least one easy, one medium and one hard question. Practice needs all three so it can adapt to each student.
            </Notice>
          </div>
        </>
      )}

      <CreateSkillDialog open={creating} onClose={() => setCreating(false)} />
    </main>
  );
}

export default function SkillsAdminPage() {
  const { user } = useAuth();
  return (
    <RequireAuth>
      {user && user.role !== "student" ? (
        <Suspense fallback={<main><LoadingBlock lines={4} /></main>}>
          <SkillsContent />
        </Suspense>
      ) : (
        <main className="narrow">
          <Notice tone="error">Only instructors and admins can manage skills.</Notice>
        </main>
      )}
    </RequireAuth>
  );
}
