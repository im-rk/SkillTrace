"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { examAdminApi, type ExamListItem } from "@/features/exam-admin/api/exam-admin.api";
import { ExamWindow } from "@/features/exam-admin/components/ExamTimeDisplay";
import { QuestionPicker } from "@/features/exam-admin/components/QuestionPicker";
import { AccessCodePanel } from "@/features/exam-admin/components/AccessCodePanel";
import { EnrollmentRoster } from "@/features/exam-admin/components/EnrollmentRoster";
import { PageHeader } from "@/components/ui/PageHeader";
import { PhaseChip } from "@/components/ui/Chip";
import { LoadingBlock, Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";
import { plural } from "@/lib/format";

function ExamDetailContent({ examId }: { examId: string }) {
  const [exam, setExam] = useState<ExamListItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const [questionCount, setQuestionCount] = useState<number | null>(null);
  const [codeCount, setCodeCount] = useState<number | null>(null);
  const [studentCount, setStudentCount] = useState<number | null>(null);
  const mountedRef = useRef(true);

  const reload = useCallback(async () => {
    try {
      const all = await examAdminApi.list();
      const found = all.find((e) => e.id === examId);
      if (!mountedRef.current) return;
      if (!found) setError("This exam does not exist.");
      else {
        setExam(found);
        setQuestionCount((current) => current ?? found.question_count);
        setStudentCount((current) => current ?? found.enrolled_count);
      }
    } catch (err) {
      if (mountedRef.current) setError(err instanceof ApiError ? err.detail : "Could not load this exam.");
    }
  }, [examId]);

  useEffect(() => {
    mountedRef.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount; setState happens after an await, guarded by mountedRef
    reload();
    return () => {
      mountedRef.current = false;
    };
  }, [reload]);

  async function handleClose() {
    if (!window.confirm("Close this exam? Students can no longer take it, and results are calculated.")) return;
    setClosing(true);
    try {
      await examAdminApi.close(examId);
      await reload();
    } catch (err) {
      if (mountedRef.current) setError(err instanceof ApiError ? err.detail : "Could not close this exam.");
    } finally {
      if (mountedRef.current) setClosing(false);
    }
  }

  if (error)
    return (
      <main className="narrow">
        <Notice tone="error">{error}</Notice>
      </main>
    );
  if (!exam)
    return (
      <main>
        <LoadingBlock lines={5} />
      </main>
    );

  const closed = exam.phase === "closed";
  const steps = [
    { done: (questionCount ?? 0) > 0, title: "Choose the questions", detail: questionCount ? plural(questionCount, "question") + " selected" : "None selected yet" },
    { done: (codeCount ?? 0) > 0, title: "Share an access code", detail: codeCount ? "Code ready to share" : "No code yet" },
    { done: (studentCount ?? 0) > 0, title: "Students join", detail: studentCount ? plural(studentCount, "student") + " joined" : "Waiting for students" },
  ];
  const current = steps.findIndex((s) => !s.done);

  return (
    <main>
      <PageHeader
        crumbs={[{ href: "/admin/exams", label: "Exams" }, { label: exam.title }]}
        eyebrow={exam.skill_name}
        title={exam.title}
        lede={
          <span className="row" style={{ gap: 12 }}>
            <PhaseChip phase={exam.phase} />
            <span>
              <ExamWindow start={exam.start_time} end={exam.end_time} /> · {exam.duration_minutes} min each
            </span>
          </span>
        }
        actions={
          <>
            <Link href={`/admin/exams/${exam.id}/results`} className="btn btn-secondary">
              <Icon name="chart" small />
              View results overview
            </Link>
            {!closed && (
              <button type="button" className="btn btn-danger" disabled={closing} onClick={handleClose}>
                {closing ? "Closing…" : "Close exam"}
              </button>
            )}
          </>
        }
      />

      {closed && (
        <div style={{ marginBottom: 20 }}>
          <Notice tone="info">This exam is closed. Results are available and the questions can no longer change.</Notice>
        </div>
      )}

      <ol className="steps" style={{ listStyle: "none", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", marginBottom: 24 }} aria-label="Exam setup">
        {steps.map((step, i) => (
          <li key={step.title} className={`step ${step.done ? "done" : !closed && i === current ? "current" : ""}`}>
            <span className="step-badge">{step.done ? <Icon name="check" small /> : i + 1}</span>
            <h2 className="h3">{step.title}</h2>
            <p>{step.detail}</p>
          </li>
        ))}
      </ol>

      <div className="split">
        <section className="card" aria-labelledby="exam-questions-title">
          <div className="card-head">
            <h2 className="h2" id="exam-questions-title">
              Questions
            </h2>
            <Link href={`/admin/skills/${exam.skill_id}`} className="link small">
              Edit the {exam.skill_name} question bank
            </Link>
          </div>
          <QuestionPicker examId={exam.id} skillId={exam.skill_id} skillName={exam.skill_name} readOnly={closed} onSaved={setQuestionCount} />
        </section>

        <div className="stack">
          <section className="card card-pad" aria-labelledby="exam-code-title">
            <h2 className="h2" id="exam-code-title" style={{ marginBottom: 14 }}>
              Access code
            </h2>
            <AccessCodePanel examId={exam.id} onChanged={setCodeCount} />
          </section>

          <section className="card" aria-labelledby="exam-students-title">
            <div className="card-head">
              <h2 className="h2" id="exam-students-title">
                Enrolled students
              </h2>
            </div>
            <EnrollmentRoster examId={exam.id} onLoaded={setStudentCount} />
          </section>
        </div>
      </div>
    </main>
  );
}

export default function ExamDetailPage({ params }: { params: Promise<{ examId: string }> }) {
  const { examId } = use(params);
  const { user } = useAuth();

  return (
    <RequireAuth>
      {user && user.role !== "student" ? (
        <ExamDetailContent examId={examId} />
      ) : (
        <main className="narrow">
          <Notice tone="error">Only instructors and admins can manage exams.</Notice>
        </main>
      )}
    </RequireAuth>
  );
}
