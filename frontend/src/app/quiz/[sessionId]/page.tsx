"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ApiError } from "@/lib/api-client";
import { practiceApi, pct, type AnswerResult, type PracticeQuestion, type QuizStatus } from "@/features/practice/api/practice.api";
import { MasteryGauge } from "@/features/practice/components/MasteryGauge";
import { PracticeQuestionCard } from "@/features/practice/components/PracticeQuestionCard";

type Outcome = QuizStatus | "exhausted";

type View =
  | { kind: "loading" }
  | { kind: "question"; question: PracticeQuestion }
  | { kind: "feedback"; question: PracticeQuestion; result: AnswerResult }
  | { kind: "done"; outcome: Outcome };

const DONE_MESSAGE: Record<Outcome, string> = {
  mastered: "You've mastered this skill!",
  exhausted: "You've answered every question available for this skill.",
  abandoned: "This practice session has ended.",
  in_progress: "",
};

function QuizContent({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [view, setView] = useState<View>({ kind: "loading" });
  const [mastery, setMastery] = useState<number | null>(null);
  const [threshold, setThreshold] = useState(0.85);
  const [counts, setCounts] = useState({ answered: 0, correct: 0 });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const loadNext = useCallback(async () => {
    try {
      const next = await practiceApi.nextQuestion(sessionId);
      if (!mounted.current) return;
      setMastery(next.mastery);
      if (next.status === "in_progress" && next.question) setView({ kind: "question", question: next.question });
      else setView({ kind: "done", outcome: next.status });
    } catch (err) {
      if (mounted.current) setError(err instanceof ApiError ? err.detail : "Could not load the next question.");
    }
  }, [sessionId]);

  useEffect(() => {
    mounted.current = true;
    async function init() {
      try {
        const session = await practiceApi.get(sessionId);
        if (!mounted.current) return;
        setMastery(session.current_mastery);
        setThreshold(session.mastery_threshold);
        setCounts({ answered: session.questions_answered, correct: session.questions_correct });
        if (session.status !== "in_progress") setView({ kind: "done", outcome: session.status });
        else await loadNext();
      } catch (err) {
        if (mounted.current) setError(err instanceof ApiError ? err.detail : "Could not load this practice session.");
      }
    }
    void init();
    return () => {
      mounted.current = false;
    };
  }, [sessionId, loadNext]);

  async function submit(question: PracticeQuestion, answer: string) {
    setSubmitting(true);
    setError(null);
    try {
      const result = await practiceApi.answer(sessionId, question.id, answer);
      setMastery(result.mastery_after);
      setCounts((c) => ({ answered: c.answered + 1, correct: c.correct + (result.is_correct ? 1 : 0) }));
      setView({ kind: "feedback", question, result });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not submit your answer.");
    } finally {
      setSubmitting(false);
    }
  }

  async function quit() {
    try {
      await practiceApi.quit(sessionId);
      router.push("/practice");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not end the session.");
    }
  }

  return (
    <main>
      <h1>Practice quiz</h1>
      {mastery !== null && <MasteryGauge mastery={mastery} threshold={threshold} />}
      <p>
        <small>
          Answered {counts.answered}, correct {counts.correct}
        </small>
      </p>
      {error && <p role="alert">{error}</p>}

      {view.kind === "loading" && !error && <p>Loading…</p>}

      {view.kind === "question" && (
        <>
          <PracticeQuestionCard key={view.question.id} question={view.question} submitting={submitting} onSubmit={(a) => submit(view.question, a)} />
          <button type="button" onClick={quit}>
            End session
          </button>
        </>
      )}

      {view.kind === "feedback" && (
        <div data-testid="answer-feedback">
          <p role="status">
            {view.result.is_correct ? "Correct!" : "Not quite."} Mastery {pct(view.result.mastery_before)}% → {pct(view.result.mastery_after)}%
          </p>
          <button
            type="button"
            onClick={() => {
              if (view.result.session_status === "in_progress") void loadNext();
              else setView({ kind: "done", outcome: view.result.session_status });
            }}
          >
            {view.result.session_status === "in_progress" ? "Next question" : "See results"}
          </button>
        </div>
      )}

      {view.kind === "done" && (
        <div data-testid="quiz-done">
          <p role="status">{DONE_MESSAGE[view.outcome]}</p>
          <Link href="/practice">Back to practice</Link> · <Link href="/progress">See my progress</Link>
        </div>
      )}
    </main>
  );
}

export default function QuizPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  return (
    <RequireAuth>
      <QuizContent sessionId={sessionId} />
    </RequireAuth>
  );
}
