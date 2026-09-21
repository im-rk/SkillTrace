"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ApiError } from "@/lib/api-client";
import {
  ENDED_SESSION_STATUSES,
  examTakingApi,
  type ExamSessionResponse,
  type StudentExamView,
} from "@/features/exam-taking/api/exam-taking.api";
import { useExamSession } from "@/features/exam-taking/hooks/useExamSession";
import { useExamTimer } from "@/features/exam-taking/hooks/useExamTimer";
import { ExamTimer } from "@/features/exam-taking/components/ExamTimer";
import { ConnectionStatusBanner } from "@/features/exam-taking/components/ConnectionStatusBanner";
import { QuestionCard } from "@/features/exam-taking/components/QuestionCard";

function ExamEnded({ examId, title, reason }: { examId: string; title: string; reason: string }) {
  return (
    <main>
      <h1>{title}</h1>
      <p role="status" data-testid="exam-ended">
        {reason}
      </p>
      <p>
        <Link href={`/exams/${examId}/results`}>View results</Link> · <Link href="/dashboard">Back to dashboard</Link>
      </p>
    </main>
  );
}

function ExamTakingContent({ examId }: { examId: string }) {
  const [exam, setExam] = useState<StudentExamView | null>(null);
  const [examSession, setExamSession] = useState<ExamSessionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [examView, session] = await Promise.all([
          examTakingApi.getExamForStudent(examId),
          examTakingApi.startExam(examId),
        ]);
        if (cancelled) return;
        setExam(examView);
        setExamSession(session);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : "Could not load this exam.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [examId]);

  if (error) return <p role="alert">{error}</p>;
  if (!exam || !examSession) return <p>Loading exam…</p>;

  if (ENDED_SESSION_STATUSES.includes(examSession.status)) {
    return <ExamEnded examId={examId} title={exam.title} reason="You have already finished this exam." />;
  }
  return <LiveExam examId={examId} exam={exam} sessionId={examSession.session_id} />;
}

function LiveExam({ examId, exam, sessionId }: { examId: string; exam: StudentExamView; sessionId: string }) {
  const [endedReason, setEndedReason] = useState<string | null>(null);
  const [confirmingFinish, setConfirmingFinish] = useState(false);
  const [finishError, setFinishError] = useState<string | null>(null);
  const { connectionState } = useExamSession(sessionId, {
    onTimeUp: () => setEndedReason("Time is up. Your exam was submitted automatically."),
  });
  const { secondsLeft, isTimeUp } = useExamTimer(sessionId);

  async function finish() {
    setFinishError(null);
    try {
      await examTakingApi.submitExam(sessionId);
      setEndedReason("Your exam has been submitted.");
    } catch (err) {
      setFinishError(err instanceof ApiError ? err.detail : "Could not submit the exam. Please try again.");
    }
  }

  if (endedReason || isTimeUp) {
    return <ExamEnded examId={examId} title={exam.title} reason={endedReason ?? "Time is up. This exam has ended."} />;
  }

  return (
    <main>
      <h1>{exam.title}</h1>
      <ConnectionStatusBanner connectionState={connectionState} />
      <ExamTimer secondsLeft={secondsLeft} connectionState={connectionState} />
      {exam.questions.length === 0 && <p>This exam has no questions yet.</p>}
      {exam.questions.map((question) => (
        <QuestionCard key={question.question_id} sessionId={sessionId} question={question} />
      ))}

      {confirmingFinish ? (
        <p>
          Submit your exam? You will not be able to change your answers.{" "}
          <button type="button" onClick={finish}>
            Yes, submit
          </button>{" "}
          <button type="button" onClick={() => setConfirmingFinish(false)}>
            Cancel
          </button>
        </p>
      ) : (
        <button type="button" onClick={() => setConfirmingFinish(true)}>
          Finish exam
        </button>
      )}
      {finishError && <p role="alert">{finishError}</p>}
    </main>
  );
}

export default function ExamTakingPage({ params }: { params: Promise<{ examId: string }> }) {
  const { examId } = use(params);
  return (
    <RequireAuth>
      <ExamTakingContent examId={examId} />
    </RequireAuth>
  );
}
