"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { examTakingApi } from "@/features/exam-taking/api/exam-taking.api";

export type SubmissionPhase = "idle" | "submitting" | "processing" | "confirmed" | "failed";

const POLL_INTERVAL_MS = 2_000;

/**
 * The fast-path submit endpoint (Phase 9) only ever returns 202 Accepted --
 * the answer is logged and queued, not graded yet. This hook keeps
 * "submitted, being processed" (processing) and "confirmed processed"
 * (confirmed) as genuinely distinct states rather than implying a
 * synchronous confirmation the backend doesn't provide.
 */
export function useSubmitAnswer(sessionId: string) {
  const [phase, setPhase] = useState<SubmissionPhase>("idle");
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
  }, []);

  // Stop polling if the component using this hook unmounts mid-poll (e.g.
  // the student navigates away) -- otherwise it keeps hitting the backend
  // and calling setState on a component that's gone.
  useEffect(() => stopPolling, [stopPolling]);

  const submit = useCallback(
    async (questionId: string, answer: string) => {
      stopPolling();
      setPhase("submitting");
      try {
        const { log_id } = await examTakingApi.submitAnswer(sessionId, questionId, answer);
        setPhase("processing");

        const poll = async () => {
          const result = await examTakingApi.getSubmissionStatus(log_id);
          if (result.status === "completed") {
            setPhase("confirmed");
          } else if (result.status === "failed") {
            setPhase("failed");
          } else {
            pollTimerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
          }
        };
        await poll();
      } catch {
        setPhase("failed");
      }
    },
    [sessionId, stopPolling],
  );

  return { phase, submit };
}
