"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { enrollmentApi, type MyExam } from "@/features/enrollment/api/enrollment.api";
import { LOCAL_TIMEZONE } from "@/lib/timezone";

const ENDED = ["submitted", "auto_submitted", "expired"];

function ExamAction({ exam }: { exam: MyExam }) {
  const finished = exam.session_status !== null && ENDED.includes(exam.session_status);
  if (finished || exam.phase === "closed") return <Link href={`/exams/${exam.exam_id}/results`}>View results</Link>;
  if (exam.phase === "upcoming") return <span>Not open yet</span>;
  if (exam.phase === "ended") return <span>Exam window closed</span>;
  return <Link href={`/exams/${exam.exam_id}`}>{exam.session_status ? "Continue exam" : "Start exam"}</Link>;
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

  if (exams === null) return <p>Loading your exams…</p>;
  if (exams.length === 0) return <p>You are not enrolled in any exams yet.</p>;

  return (
    <ul>
      {exams.map((exam) => (
        <li key={exam.exam_id} data-testid="my-exam">
          <strong>{exam.title}</strong> — {new Date(exam.start_time).toLocaleString()} to{" "}
          {new Date(exam.end_time).toLocaleString()} ({LOCAL_TIMEZONE}), {exam.duration_minutes} min —{" "}
          <ExamAction exam={exam} />
        </li>
      ))}
    </ul>
  );
}
