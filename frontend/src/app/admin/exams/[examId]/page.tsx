"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { examAdminApi, type Exam } from "@/features/exam-admin/api/exam-admin.api";
import { ExamTimeDisplay } from "@/features/exam-admin/components/ExamTimeDisplay";
import { QuestionAssignmentPanel } from "@/features/exam-admin/components/QuestionAssignmentPanel";
import { AccessCodePanel } from "@/features/exam-admin/components/AccessCodePanel";
import { EnrollmentRoster } from "@/features/exam-admin/components/EnrollmentRoster";

function ExamDetailContent({ examId }: { examId: string }) {
  const [exam, setExam] = useState<Exam | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const mountedRef = useRef(true);

  const reload = useCallback(async () => {
    try {
      const loaded = await examAdminApi.get(examId);
      if (mountedRef.current) setExam(loaded);
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

  if (error) return <p role="alert">{error}</p>;
  if (!exam) return <p>Loading…</p>;

  return (
    <main>
      <h1>{exam.title}</h1>
      <p>
        Status: {exam.status} — <ExamTimeDisplay iso={exam.start_time} /> to <ExamTimeDisplay iso={exam.end_time} />
      </p>
      {exam.status !== "closed" && (
        <button type="button" disabled={closing} onClick={handleClose}>
          {closing ? "Closing…" : "Close exam"}
        </button>
      )}
      <Link href={`/admin/exams/${exam.id}/results`}>View results overview</Link>

      <section>
        <h2>Questions</h2>
        <QuestionAssignmentPanel examId={exam.id} skillId={exam.skill_id} />
      </section>

      <section>
        <h2>Access codes</h2>
        <AccessCodePanel examId={exam.id} />
      </section>

      <section>
        <h2>Enrolled students</h2>
        <EnrollmentRoster examId={exam.id} />
      </section>
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
        <p role="alert">Only instructors and admins can manage exams.</p>
      )}
    </RequireAuth>
  );
}
