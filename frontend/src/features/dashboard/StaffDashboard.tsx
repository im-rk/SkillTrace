"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { skillsApi, type Skill, type SkillReadiness } from "@/features/question-bank-admin/api/skills.api";
import { examAdminApi, type ExamListItem } from "@/features/exam-admin/api/exam-admin.api";
import { PageHeader } from "@/components/ui/PageHeader";
import { PhaseChip } from "@/components/ui/Chip";
import { EmptyState, LoadingBlock } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";
import { formatWindow, greeting, plural } from "@/lib/format";

interface SkillWithReadiness {
  skill: Skill;
  readiness: SkillReadiness;
}

const total = (r: SkillReadiness) => r.counts.easy + r.counts.medium + r.counts.hard;

export function StaffDashboard() {
  const { user } = useAuth();
  const [skills, setSkills] = useState<SkillWithReadiness[] | null>(null);
  const [exams, setExams] = useState<ExamListItem[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [loadedSkills, loadedExams] = await Promise.all([skillsApi.list(), examAdminApi.list()]);
      const withReadiness = await Promise.all(loadedSkills.map(async (skill) => ({ skill, readiness: await skillsApi.readiness(skill.id) })));
      if (cancelled) return;
      setSkills(withReadiness);
      setExams(loadedExams);
    }
    load().catch(() => {
      if (!cancelled) {
        setSkills([]);
        setExams([]);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const loading = skills === null || exams === null;
  const skillCount = skills?.length ?? 0;
  const questionCount = (skills ?? []).reduce((n, s) => n + total(s.readiness), 0);
  const readyCount = (skills ?? []).filter((s) => s.readiness.ready).length;
  const needsQuestions = (skills ?? []).find((s) => !s.readiness.ready);
  const liveCount = (exams ?? []).filter((e) => e.phase === "live").length;
  const closed = (exams ?? []).find((e) => e.phase === "closed" && e.enrolled_count > 0);

  const done = [skillCount > 0, readyCount > 0, (exams ?? []).length > 0, Boolean(closed)];
  const current = done.findIndex((d) => !d);

  const stepClass = (i: number) => `step ${done[i] ? "done" : i === current ? "current" : ""}`;

  return (
    <main>
      <PageHeader
        eyebrow="Overview"
        title={`${greeting()}, ${user?.display_name.split(" ")[0] ?? ""}`}
        lede="Four steps take you from an empty account to a class with measured mastery."
      />

      {loading ? (
        <LoadingBlock lines={4} />
      ) : (
        <>
          <ol className="steps" style={{ listStyle: "none" }} aria-label="Setup steps">
            <li className={stepClass(0)}>
              <span className="step-badge">{done[0] ? <Icon name="check" small /> : 1}</span>
              <h2 className="h3">Create a skill</h2>
              <p>A skill is one topic students should master, such as Fractions. Mastery is tracked per skill.</p>
              <div className="step-foot">
                <p className="small" style={{ marginBottom: 8 }}>
                  <b>{plural(skillCount, "skill")}</b>
                </p>
                <Link href="/admin/skills?new=1" className={`btn btn-sm ${current === 0 ? "btn-primary" : "btn-secondary"}`}>
                  {skillCount === 0 ? "Create your first skill" : "Add a skill"}
                </Link>
              </div>
            </li>
            <li className={stepClass(1)}>
              <span className="step-badge">{done[1] ? <Icon name="check" small /> : 2}</span>
              <h2 className="h3">Build its question bank</h2>
              <p>Add easy, medium and hard questions. The system picks difficulty from each student&apos;s mastery.</p>
              <div className="step-foot">
                <p className="small" style={{ marginBottom: 8 }}>
                  <b>{plural(questionCount, "question")}</b> · {readyCount} of {plural(skillCount, "skill")} ready
                </p>
                {needsQuestions && (
                  <p className="muted small" style={{ marginBottom: 8, overflowWrap: "anywhere" }}>
                    Next: {needsQuestions.skill.name}
                  </p>
                )}
                <Link
                  href={needsQuestions ? `/admin/skills/${needsQuestions.skill.id}` : "/admin/skills"}
                  className={`btn btn-sm ${current === 1 ? "btn-primary" : "btn-secondary"}`}
                >
                  {needsQuestions ? "Add questions" : "Manage questions"}
                </Link>
              </div>
            </li>
            <li className={stepClass(2)}>
              <span className="step-badge">{done[2] ? <Icon name="check" small /> : 3}</span>
              <h2 className="h3">Schedule an exam</h2>
              <p>Pick a skill, choose its questions, set the time window, and share the access code.</p>
              <div className="step-foot">
                <p className="small" style={{ marginBottom: 8 }}>
                  <b>{plural((exams ?? []).length, "exam")}</b>
                  {liveCount > 0 && ` · ${liveCount} live now`}
                </p>
                <Link href="/admin/exams/new" className={`btn btn-sm ${current === 2 ? "btn-primary" : "btn-secondary"}`}>
                  New exam
                </Link>
              </div>
            </li>
            <li className={stepClass(3)}>
              <span className="step-badge">{done[3] ? <Icon name="check" small /> : 4}</span>
              <h2 className="h3">Review the results</h2>
              <p>Close the exam to see scores, each student&apos;s mastery, and which questions worked.</p>
              <div className="step-foot">
                <p className="small" style={{ marginBottom: 8 }}>
                  {closed ? <b>{closed.title}</b> : <span className="muted">Available once an exam is closed</span>}
                </p>
                {closed ? (
                  <Link href={`/admin/exams/${closed.id}/results`} className={`btn btn-sm ${current === 3 ? "btn-primary" : "btn-secondary"}`}>
                    Open results
                  </Link>
                ) : (
                  <span className="btn btn-sm btn-secondary" aria-disabled="true" style={{ opacity: 0.5, pointerEvents: "none" }}>
                    Open results
                  </span>
                )}
              </div>
            </li>
          </ol>

          <div className="grid grid-2" style={{ marginTop: 28, alignItems: "start" }}>
            <section className="card" aria-labelledby="recent-exams">
              <div className="card-head">
                <h2 className="h2" id="recent-exams">
                  Exams
                </h2>
                <Link href="/admin/exams" className="link small">
                  All exams
                </Link>
              </div>
              {(exams ?? []).length === 0 ? (
                <EmptyState icon="calendar" title="No exams yet">
                  Once a skill has questions, schedule your first exam.
                </EmptyState>
              ) : (
                <ul className="divided" style={{ listStyle: "none" }}>
                  {(exams ?? []).slice(0, 5).map((exam) => (
                    <li key={exam.id}>
                      <Link href={`/admin/exams/${exam.id}`} className="q-row" style={{ display: "grid" }}>
                        <div>
                          <div className="row">
                            <strong>{exam.title}</strong>
                            <PhaseChip phase={exam.phase} />
                          </div>
                          <div className="q-meta muted small">
                            {exam.skill_name} · {plural(exam.question_count, "question")} · {plural(exam.enrolled_count, "student")}
                          </div>
                          <div className="muted small">{formatWindow(exam.start_time, exam.end_time)}</div>
                        </div>
                        <Icon name="arrow" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="card" aria-labelledby="skills-overview">
              <div className="card-head">
                <h2 className="h2" id="skills-overview">
                  Skills
                </h2>
                <Link href="/admin/skills" className="link small">
                  All skills
                </Link>
              </div>
              {(skills ?? []).length === 0 ? (
                <EmptyState icon="book" title="No skills yet">
                  Start by creating the first skill you want to teach.
                </EmptyState>
              ) : (
                <ul className="divided" style={{ listStyle: "none" }}>
                  {(skills ?? []).map(({ skill, readiness }) => (
                    <li key={skill.id}>
                      <Link href={`/admin/skills/${skill.id}`} className="q-row" style={{ display: "grid" }}>
                        <div>
                          <div className="row">
                            <strong>{skill.name}</strong>
                            {readiness.ready ? <span className="chip chip-ok">Ready</span> : <span className="chip chip-warn">Needs {readiness.missing_tiers.join(", ")}</span>}
                          </div>
                          <div className="q-meta muted small">
                            {readiness.counts.easy} easy · {readiness.counts.medium} medium · {readiness.counts.hard} hard
                          </div>
                        </div>
                        <Icon name="arrow" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <section className="card card-pad" style={{ marginTop: 28 }} aria-labelledby="how-it-works">
            <h2 className="h2" id="how-it-works">
              How a student&apos;s mastery is measured
            </h2>
            <div className="grid grid-3" style={{ marginTop: 16 }}>
              <div>
                <p className="eyebrow">1 · Each answer is evidence</p>
                <p className="muted small">
                  A correct answer could be a lucky guess; a wrong one could be a slip. The model weighs both using the skill&apos;s guess and slip rates.
                </p>
              </div>
              <div>
                <p className="eyebrow">2 · Belief updates (Bayes)</p>
                <p className="muted small">
                  After every answer the probability that the student has mastered the skill is recomputed, then nudged up by the chance they just learned it.
                </p>
              </div>
              <div>
                <p className="eyebrow">3 · The estimate steers practice</p>
                <p className="muted small">
                  Below 40% the student gets easy questions, up to the goal medium ones; at the goal (85% by default) the skill counts as mastered.
                </p>
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
