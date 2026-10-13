"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ApiError } from "@/lib/api-client";
import { practiceApi, type AnswerResult, type PracticeQuestion, type QuizStatus } from "@/features/practice/api/practice.api";
import { MasteryGauge } from "@/features/practice/components/MasteryGauge";
import { PracticeQuestionCard } from "@/features/practice/components/PracticeQuestionCard";
import { LoadingBlock, Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";
import { pct } from "@/lib/format";

type Outcome = QuizStatus | "exhausted";

type View =
  | { kind: "loading" }
  | { kind: "question"; question: PracticeQuestion }
  | { kind: "feedback"; question: PracticeQuestion; result: AnswerResult }
  | { kind: "done"; outcome: Outcome };

const DONE: Record<Outcome, { title: string; body: string }> = {
  mastered: { title: "You've mastered this skill!", body: "Your estimated mastery reached the goal. Nice work." },
  exhausted: { title: "You've answered every question available for this skill.", body: "Ask your instructor for more questions, or review your progress." },
  abandoned: { title: "This practice session has ended.", body: "Your mastery is saved. Continue whenever you like." },
  in_progress: { title: "", body: "" },
};

function QuizContent({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [view, setView] = useState<View>({ kind: "loading" });
  const [mastery, setMastery] = useState<number | null>(null);
  const [delta, setDelta] = useState<number | null>(null);
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
      setDelta(pct(result.mastery_after) - pct(result.mastery_before));
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
    <main className="focus">
      <div className="row-between" style={{ marginBottom: 20 }}>
        <Link href="/practice" className="btn btn-ghost btn-sm" style={{ marginLeft: -12 }}>
          ← Practice
        </Link>
        {(view.kind === "question" || view.kind === "feedback") && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={quit}>
            End session
          </button>
        )}
      </div>

      <div className="stack">
        {mastery !== null && <MasteryGauge mastery={mastery} threshold={threshold} delta={delta} answered={counts.answered} correct={counts.correct} />}
        {error && <Notice tone="error">{error}</Notice>}
        {view.kind === "loading" && !error && <LoadingBlock lines={4} />}

        {view.kind === "question" && (
          <PracticeQuestionCard key={view.question.id} question={view.question} submitting={submitting} locked={false} onSubmit={(a) => submit(view.question, a)} />
        )}

        {view.kind === "feedback" && (
          <>
            <PracticeQuestionCard key={view.question.id} question={view.question} submitting={false} locked onSubmit={() => {}} />
            <div data-testid="answer-feedback">
              <div className={`feedback ${view.result.is_correct ? "right" : "wrong"}`} role="status">
                <Icon name={view.result.is_correct ? "check" : "x"} />
                <div>
                  <div className="verdict">{view.result.is_correct ? "Correct!" : "Not quite."}</div>
                  <div className="num">
                    Mastery {pct(view.result.mastery_before)}% → {pct(view.result.mastery_after)}%
                  </div>
                </div>
              </div>
              <div className="form-actions" style={{ marginTop: 16 }}>
                <button
                  type="button"
                  className="btn btn-primary btn-lg"
                  onClick={() => {
                    if (view.result.session_status === "in_progress") void loadNext();
                    else setView({ kind: "done", outcome: view.result.session_status });
                  }}
                >
                  {view.result.session_status === "in_progress" ? "Next question" : "See results"}
                </button>
              </div>
            </div>
          </>
        )}

        {view.kind === "done" && (
          <div className="card card-pad" data-testid="quiz-done" style={{ textAlign: "center", padding: "40px 24px" }}>
            <span className="icon-wrap" style={{ display: "inline-grid", placeItems: "center", width: 56, height: 56, borderRadius: "50%", background: "var(--ok-soft)", color: "var(--ok)", marginBottom: 16 }}>
              <Icon name={view.outcome === "mastered" ? "check" : "flag"} />
            </span>
            <h2 className="title" style={{ fontSize: 26 }} role="status">
              {DONE[view.outcome].title}
            </h2>
            <p className="muted" style={{ margin: "8px auto 24px", maxWidth: "46ch" }}>
              {DONE[view.outcome].body}
            </p>
            <div className="row" style={{ justifyContent: "center" }}>
              <Link href="/practice" className="btn btn-primary">
                Back to practice
              </Link>
              <Link href="/progress" className="btn btn-secondary">
                See my progress
              </Link>
            </div>
          </div>
        )}
      </div>
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
