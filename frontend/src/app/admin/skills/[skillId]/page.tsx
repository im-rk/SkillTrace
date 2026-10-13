"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { skillsApi, type Skill, type SkillReadiness, type StudentMasteryRow } from "@/features/question-bank-admin/api/skills.api";
import { questionBankApi, type Question } from "@/features/question-bank-admin/api/question-bank.api";
import { QuestionList } from "@/features/question-bank-admin/components/QuestionList";
import { QuestionEditor } from "@/features/question-bank-admin/components/QuestionEditor";
import { AiDraftPanel } from "@/features/question-bank-admin/components/AiDraftPanel";
import { ImportPanel } from "@/features/question-bank-admin/components/ImportPanel";
import { BktSettings } from "@/features/question-bank-admin/components/BktSettings";
import { SkillStudents } from "@/features/question-bank-admin/components/SkillStudents";
import { PageHeader } from "@/components/ui/PageHeader";
import { Tabs } from "@/components/ui/Tabs";
import { Chip } from "@/components/ui/Chip";
import { LoadingBlock, Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";

type TabId = "questions" | "model" | "students";

function ReadinessStrip({ readiness }: { readiness: SkillReadiness }) {
  return (
    <section className="card card-pad" aria-label="Question bank readiness" style={{ marginBottom: 24 }}>
      <div className="row-between" style={{ marginBottom: 14 }}>
        <div>
          <h2 className="h2">Question bank</h2>
          <p className="muted small">Practice needs at least one question in each difficulty so it can adapt to every student.</p>
        </div>
        {readiness.ready ? <Chip tone="ok">Ready for practice and exams</Chip> : <Chip tone="warn">Not ready yet</Chip>}
      </div>
      <div className="tiers">
        {(["easy", "medium", "hard"] as const).map((tier) => (
          <div key={tier} className={`tier ${readiness.counts[tier] === 0 ? "empty-tier" : ""}`}>
            <b className="num">{readiness.counts[tier]}</b>
            <span style={{ textTransform: "capitalize" }}>{tier}</span>
            {readiness.counts[tier] === 0 && <span> — add some</span>}
          </div>
        ))}
      </div>
      {!readiness.ready && (
        <div style={{ marginTop: 14 }}>
          <Notice tone="warn" role="alert">
            Not ready for adaptive practice: no {readiness.missing_tiers.join(" or ")} questions. Add some below.
          </Notice>
        </div>
      )}
    </section>
  );
}

function SkillWorkspace({ skillId }: { skillId: string }) {
  const [skill, setSkill] = useState<Skill | null | undefined>(undefined);
  const [readiness, setReadiness] = useState<SkillReadiness | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [students, setStudents] = useState<StudentMasteryRow[] | null>(null);
  const [tab, setTab] = useState<TabId>("questions");
  const [editing, setEditing] = useState(false);
  const [panel, setPanel] = useState<"ai" | "import" | null>(null);

  const load = useCallback(async () => {
    const skills = await skillsApi.list();
    const found = skills.find((s) => s.id === skillId) ?? null;
    setSkill(found);
    if (!found) return;
    const [r, q, o] = await Promise.all([skillsApi.readiness(skillId), questionBankApi.list(skillId), skillsApi.overview(skillId)]);
    setReadiness(r);
    setQuestions(q);
    setStudents(o);
  }, [skillId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount; setState happens after an await
    load();
  }, [load]);

  if (skill === undefined)
    return (
      <main>
        <LoadingBlock lines={5} />
      </main>
    );
  if (skill === null)
    return (
      <main className="narrow">
        <Notice tone="error">This skill does not exist, or was deleted.</Notice>
        <p style={{ marginTop: 16 }}>
          <Link href="/admin/skills" className="link">
            ← Back to skills
          </Link>
        </p>
      </main>
    );

  return (
    <main>
      <PageHeader
        crumbs={[{ href: "/admin/skills", label: "Skills" }, { label: skill.name }]}
        eyebrow="Skill"
        title={skill.name}
        lede={skill.description ?? undefined}
        actions={
          <Link href={`/admin/exams/new?skill=${skill.id}`} className={`btn ${readiness?.ready ? "btn-primary" : "btn-secondary"}`}>
            <Icon name="calendar" small />
            Create an exam from this skill
          </Link>
        }
      />

      {readiness && <ReadinessStrip readiness={readiness} />}

      <Tabs
        active={tab}
        onChange={(id) => setTab(id as TabId)}
        tabs={[
          { id: "questions", label: "Questions", count: questions.length },
          { id: "model", label: "Learning model" },
          { id: "students", label: "Students", count: students?.length ?? 0 },
        ]}
      >
        {tab === "questions" && (
          <div className="stack">
            <div className="row">
              <button type="button" className="btn btn-primary" onClick={() => setEditing(true)}>
                <Icon name="plus" small />
                Add question
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setPanel(panel === "ai" ? null : "ai")} aria-expanded={panel === "ai"}>
                <Icon name="pencil" small />
                Draft with AI
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setPanel(panel === "import" ? null : "import")} aria-expanded={panel === "import"}>
                <Icon name="upload" small />
                Import file
              </button>
            </div>

            {panel === "ai" && <AiDraftPanel skillId={skill.id} onSaved={load} onClose={() => setPanel(null)} />}
            {panel === "import" && <ImportPanel skillId={skill.id} onImported={load} onClose={() => setPanel(null)} />}

            <section className="card" aria-label="Questions in this skill">
              <QuestionList questions={questions} onDeleted={load} />
            </section>
          </div>
        )}

        {tab === "model" && <BktSettings key={skill.id} skill={skill} onChanged={load} />}
        {tab === "students" && <SkillStudents rows={students} threshold={skill.mastery_threshold} />}
      </Tabs>

      <QuestionEditor skillId={skill.id} open={editing} onClose={() => setEditing(false)} onSaved={load} />
    </main>
  );
}

export default function SkillWorkspacePage({ params }: { params: Promise<{ skillId: string }> }) {
  const { skillId } = use(params);
  const { user } = useAuth();
  return (
    <RequireAuth>
      {user && user.role !== "student" ? (
        <SkillWorkspace skillId={skillId} />
      ) : (
        <main className="narrow">
          <Notice tone="error">Only instructors and admins can manage skills.</Notice>
        </main>
      )}
    </RequireAuth>
  );
}
