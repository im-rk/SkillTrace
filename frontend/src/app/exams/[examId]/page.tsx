"use client";

import { use, useEffect, useState } from "react";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ApiError } from "@/lib/api-client";
import { examTakingApi, type ExamSessionResponse, type StudentExamView } from "@/features/exam-taking/api/exam-taking.api";
import { useExamSession } from "@/features/exam-taking/hooks/useExamSession";
import { useExamTimer } from "@/features/exam-taking/hooks/useExamTimer";
import { ExamTimer } from "@/features/exam-taking/components/ExamTimer";
import { ConnectionStatusBanner } from "@/features/exam-taking/components/ConnectionStatusBanner";
import { QuestionCard } from "@/features/exam-taking/components/QuestionCard";

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

  return <ExamSessionView exam={exam} sessionId={examSession.session_id} />;
}

function ExamSessionView({ exam, sessionId }: { exam: StudentExamView; sessionId: string }) {
  const { connectionState } = useExamSession(sessionId);
  const { secondsLeft, isTimeUp } = useExamTimer(sessionId);

  return (
    <main>
      <h1>{exam.title}</h1>
      <ConnectionStatusBanner connectionState={connectionState} />
      <ExamTimer secondsLeft={secondsLeft} connectionState={connectionState} />
      {isTimeUp ? (
        <p role="alert">Time&apos;s up. This exam has ended.</p>
      ) : (
        exam.questions.map((question) => (
          <QuestionCard key={question.question_id} sessionId={sessionId} question={question} />
        ))
      )}
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
