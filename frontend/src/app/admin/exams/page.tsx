"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { examAdminApi, type ExamListItem } from "@/features/exam-admin/api/exam-admin.api";
import { PageHeader } from "@/components/ui/PageHeader";
import { Chip, PhaseChip } from "@/components/ui/Chip";
import { EmptyState, LoadingBlock, Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";
import { formatWindow, plural } from "@/lib/format";

function ExamRow({ exam }: { exam: ExamListItem }) {
  const needsQuestions = exam.question_count === 0 && exam.phase !== "closed";
  return (
    <li>
      <Link href={`/admin/exams/${exam.id}`} className="q-row" style={{ display: "grid" }}>
        <div>
          <div className="row">
            <strong>{exam.title}</strong>
            <PhaseChip phase={exam.phase} />
            {needsQuestions && <Chip tone="warn">No questions yet</Chip>}
          </div>
          <div className="q-meta muted small">
            <span>{exam.skill_name}</span>
            <span aria-hidden="true">·</span>
            <span>{plural(exam.question_count, "question")}</span>
            <span aria-hidden="true">·</span>
            <span>{plural(exam.enrolled_count, "student")} joined</span>
          </div>
          <div className="muted small" style={{ marginTop: 2 }}>
            <Icon name="calendar" small /> {formatWindow(exam.start_time, exam.end_time)} · {exam.duration_minutes} min each
          </div>
        </div>
        <Icon name="arrow" />
      </Link>
    </li>
  );
}

function ExamsContent() {
  const [exams, setExams] = useState<ExamListItem[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    examAdminApi.list().then((rows) => !cancelled && setExams(rows));
    return () => {
      cancelled = true;
    };
  }, []);

  const groups: { title: string; rows: ExamListItem[] }[] = [
    { title: "Live now", rows: (exams ?? []).filter((e) => e.phase === "live") },
    { title: "Upcoming", rows: (exams ?? []).filter((e) => e.phase === "upcoming") },
    { title: "Finished", rows: (exams ?? []).filter((e) => e.phase === "ended" || e.phase === "closed") },
  ].filter((g) => g.rows.length > 0);

  return (
    <main>
      <PageHeader
        eyebrow="Exams"
        title="Exams"
        lede="An exam tests one skill in a time window. Students join with an access code, and every answer feeds their mastery of that skill."
        actions={
          <Link href="/admin/exams/new" className="btn btn-primary">
            <Icon name="plus" small />
            New exam
          </Link>
        }
      />

      {exams === null && <LoadingBlock lines={4} />}
      {exams?.length === 0 && (
        <div className="card">
          <EmptyState
            icon="calendar"
            title="No exams yet"
            action={
              <Link href="/admin/exams/new" className="btn btn-primary">
                Schedule an exam
              </Link>
            }
          >
            Pick a skill that has questions, set a time window, and share the access code.
          </EmptyState>
        </div>
      )}

      <div className="stack">
        {groups.map((group) => (
          <section key={group.title} aria-label={group.title}>
            <h2 className="eyebrow" style={{ marginBottom: 10 }}>
              {group.title} · {group.rows.length}
            </h2>
            <ul className="card divided" style={{ listStyle: "none" }}>
              {group.rows.map((exam) => (
                <ExamRow key={exam.id} exam={exam} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </main>
  );
}

export default function ExamAdminPage() {
  const { user } = useAuth();
  return (
    <RequireAuth>
      {user && user.role !== "student" ? (
        <ExamsContent />
      ) : (
        <main className="narrow">
          <Notice tone="error">Only instructors and admins can manage exams.</Notice>
        </main>
      )}
    </RequireAuth>
  );
}
