"use client";

import { useEffect, useState } from "react";
import { examTakingApi } from "@/features/exam-taking/api/exam-taking.api";

const RESYNC_INTERVAL_MS = 15_000;
const TICK_INTERVAL_MS = 1_000;

/**
 * Never end the exam because a local `setInterval` tick reached zero. This hook
 * ticks locally only for a smooth display between syncs; the remaining time always
 * comes from a periodic resync against the server-computed elapsed time
 * (live_session_gateway.service.compute_elapsed_active_time, pauses excluded).
 *
 * The authoritative end-of-exam signal is the server's `time_up` WebSocket push
 * (see useExamSession). This hook's resync reaching zero is the fallback for when
 * the socket is down at that moment -- still a fresh server value, never a local guess.
 */
export function useExamTimer(sessionId: string) {
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const isTimeUp = secondsLeft !== null && secondsLeft <= 0;

  useEffect(() => {
    let cancelled = false;
    let resyncTimer: ReturnType<typeof setInterval> | null = null;
    let tickTimer: ReturnType<typeof setInterval> | null = null;

    async function resync() {
      const timing = await examTakingApi.getSessionTiming(sessionId);
      if (cancelled) return;
      const remaining = timing.total_duration_seconds - timing.elapsed_active_seconds;
      setSecondsLeft(remaining);
      if (remaining <= 0) {
        // Exam's over -- stop polling and ticking, there's nothing left to track.
        if (resyncTimer) clearInterval(resyncTimer);
        if (tickTimer) clearInterval(tickTimer);
      }
    }

    resync();
    resyncTimer = setInterval(resync, RESYNC_INTERVAL_MS);
    tickTimer = setInterval(() => {
      setSecondsLeft((s) => (s !== null && s > 0 ? s - 1 : s));
    }, TICK_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (resyncTimer) clearInterval(resyncTimer);
      if (tickTimer) clearInterval(tickTimer);
    };
  }, [sessionId]);

  return { secondsLeft, isTimeUp };
}
