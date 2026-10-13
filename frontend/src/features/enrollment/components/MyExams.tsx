"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { enrollmentApi, type MyExam } from "@/features/enrollment/api/enrollment.api";
import { PhaseChip } from "@/components/ui/Chip";
import { EmptyState, LoadingBlock } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";
import { formatWindow } from "@/lib/format";
import { LOCAL_TIMEZONE } from "@/lib/timezone";

const ENDED = ["submitted", "auto_submitted", "expired"];

function ExamAction({ exam }: { exam: MyExam }) {
  const finished = exam.session_status !== null && ENDED.includes(exam.session_status);
  if (finished || exam.phase === "closed")
    return (
      <Link href={`/exams/${exam.exam_id}/results`} className="btn btn-secondary btn-sm">
        View results
      </Link>
    );
  if (exam.phase === "upcoming") return <span className="muted small">Not open yet</span>;
  if (exam.phase === "ended") return <span className="muted small">Exam window closed</span>;
  return (
    <Link href={`/exams/${exam.exam_id}`} className="btn btn-primary btn-sm">
      <Icon name="play" small />
      {exam.session_status ? "Continue exam" : "Start exam"}
    </Link>
  );
}

export function MyExams() {
  const [exams, setExams] = useState<MyExam[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    enrollmentApi.myExams().then((rows) => {
      if (!cancelled) setExams(rows);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (exams === null) return <div className="card-body"><LoadingBlock /></div>;
  if (exams.length === 0)
    return (
      <EmptyState icon="calendar" title="No exams yet">
        When your instructor gives you an access code, enter it under Join exam and the exam will appear here.
      </EmptyState>
    );

  return (
    <ul className="divided" style={{ listStyle: "none" }}>
      {exams.map((exam) => (
        <li key={exam.exam_id} data-testid="my-exam" className="q-row">
          <div>
            <div className="row">
              <strong>{exam.title}</strong>
              <PhaseChip phase={exam.phase} />
            </div>
            <div className="q-meta muted small">
              <Icon name="calendar" small />
              {formatWindow(exam.start_time, exam.end_time)} · {exam.duration_minutes} min · {LOCAL_TIMEZONE}
            </div>
          </div>
          <ExamAction exam={exam} />
        </li>
      ))}
    </ul>
  );
}
