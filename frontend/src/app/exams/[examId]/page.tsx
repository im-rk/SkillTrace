"use client";

import { use, useCallback, useEffect, useState } from "react";
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
import { LoadingBlock, Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";

function ExamEnded({ examId, title, reason }: { examId: string; title: string; reason: string }) {
  return (
    <main className="focus">
      <div className="card" style={{ textAlign: "center", padding: "48px 24px" }}>
        <span style={{ display: "inline-grid", placeItems: "center", width: 56, height: 56, borderRadius: "50%", background: "var(--brand-soft)", color: "var(--brand)", marginBottom: 16 }}>
          <Icon name="flag" />
        </span>
        <h1 className="title" style={{ fontSize: 26 }}>
          {title}
        </h1>
        <p role="status" data-testid="exam-ended" className="muted" style={{ margin: "10px auto 26px", maxWidth: "46ch" }}>
          {reason}
        </p>
        <div className="row" style={{ justifyContent: "center" }}>
          <Link href={`/exams/${examId}/results`} className="btn btn-primary">
            View results
          </Link>
          <Link href="/dashboard" className="btn btn-secondary">
            Back to dashboard
          </Link>
        </div>
      </div>
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
        const [examView, session] = await Promise.all([examTakingApi.getExamForStudent(examId), examTakingApi.startExam(examId)]);
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

  if (error)
    return (
      <main className="focus">
        <Notice tone="error">{error}</Notice>
        <p style={{ marginTop: 16 }}>
          <Link href="/dashboard" className="link">
            ← Back to dashboard
          </Link>
        </p>
      </main>
    );
  if (!exam || !examSession)
    return (
      <main className="focus">
        <LoadingBlock lines={5} />
      </main>
    );

  if (ENDED_SESSION_STATUSES.includes(examSession.status)) {
    return <ExamEnded examId={examId} title={exam.title} reason="You have already finished this exam." />;
  }
  return <LiveExam examId={examId} exam={exam} sessionId={examSession.session_id} />;
}

function LiveExam({ examId, exam, sessionId }: { examId: string; exam: StudentExamView; sessionId: string }) {
  const [endedReason, setEndedReason] = useState<string | null>(null);
  const [confirmingFinish, setConfirmingFinish] = useState(false);
  const [finishError, setFinishError] = useState<string | null>(null);
  const [answered, setAnswered] = useState<Set<string>>(new Set());
  const { connectionState } = useExamSession(sessionId, {
    onTimeUp: () => setEndedReason("Time is up. Your exam was submitted automatically."),
  });
  const { secondsLeft, isTimeUp } = useExamTimer(sessionId);

  const markAnswered = useCallback((questionId: string) => {
    setAnswered((current) => (current.has(questionId) ? current : new Set(current).add(questionId)));
  }, []);

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

  const total = exam.questions.length;

  return (
    <>
      <div className="exam-bar">
        <div className="exam-bar-inner">
          <div style={{ flex: 1, minWidth: 160 }}>
            <h1 className="h2" style={{ lineHeight: 1.25 }}>
              {exam.title}
            </h1>
            <p className="muted small num">
              {answered.size} of {total} answered
            </p>
          </div>
          <ExamTimer secondsLeft={secondsLeft} connectionState={connectionState} />
        </div>
      </div>

      <main className="focus">
        <div className="stack">
          <ConnectionStatusBanner connectionState={connectionState} />
          {total === 0 && <Notice tone="warn">This exam has no questions yet.</Notice>}

          {exam.questions.map((question, index) => (
            <QuestionCard key={question.question_id} sessionId={sessionId} question={question} index={index} total={total} onConfirmed={markAnswered} />
          ))}

          <section className="card card-pad">
            {confirmingFinish ? (
              <div className="stack-sm">
                <p>
                  <b>Submit your exam?</b> You will not be able to change your answers.
                  {answered.size < total && <span className="muted"> You have answered {answered.size} of {total} questions.</span>}
                </p>
                <div className="row">
                  <button type="button" className="btn btn-primary" onClick={finish}>
                    Yes, submit
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={() => setConfirmingFinish(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="row-between">
                <p className="muted small">When you have answered everything you want to, finish the exam.</p>
                <button type="button" className="btn btn-primary btn-lg" onClick={() => setConfirmingFinish(true)}>
                  Finish exam
                </button>
              </div>
            )}
            {finishError && (
              <div style={{ marginTop: 12 }}>
                <Notice tone="error">{finishError}</Notice>
              </div>
            )}
          </section>
        </div>
      </main>
    </>
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
