"use client";

import { useEffect, useRef, useState } from "react";

export type ConnectionState = "connecting" | "connected" | "reconnecting" | "disconnected_final";

const WS_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/^http/, "ws");
const MAX_RETRIES = 5;
const HEARTBEAT_INTERVAL_MS = 10_000;

/**
 * Mirrors the backend's WebSocket state machine (docs/adr/0010): a 4403
 * close means Phase 8's pre-accept authorization check rejected us -- that's
 * not a transient network problem, so it gets no retry. Every other close
 * reason gets exponential backoff, capped, up to MAX_RETRIES.
 *
 * No token in the URL: the browser attaches the httpOnly auth cookie to the
 * WebSocket handshake automatically (see enrollment.deps.verify_exam_access_ws's
 * cookie fallback) -- unlike the phase doc's reference snippet, this app
 * never has the JWT in JS to put there.
 */
export function useExamSession(sessionId: string, options: { onTimeUp?: () => void } = {}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const onTimeUpRef = useRef(options.onTimeUp);
  useEffect(() => {
    onTimeUpRef.current = options.onTimeUp;
  });

  useEffect(() => {
    let unmounted = false;
    let retryCount = 0;
    let ws: WebSocket | null = null;
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      ws = new WebSocket(`${WS_BASE_URL}/ws/exam-sessions/${sessionId}`);

      ws.onopen = () => {
        setConnectionState("connected");
        retryCount = 0;
        heartbeatTimer = setInterval(() => {
          ws?.send(JSON.stringify({ type: "heartbeat" }));
        }, HEARTBEAT_INTERVAL_MS);
      };

      // The server pushes time_up when this session is auto-submitted (out of time, or the
      // instructor closed the exam). It is the authoritative end-of-exam signal.
      ws.onmessage = (event) => {
        try {
          if (JSON.parse(event.data).type === "time_up") onTimeUpRef.current?.();
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onclose = (event) => {
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        if (unmounted) return;

        if (event.code === 4403) {
          setConnectionState("disconnected_final");
          return;
        }
        if (retryCount < MAX_RETRIES) {
          setConnectionState("reconnecting");
          const backoffMs = Math.min(1000 * 2 ** retryCount, 30000);
          reconnectTimer = setTimeout(() => {
            retryCount += 1;
            connect();
          }, backoffMs);
        } else {
          setConnectionState("disconnected_final");
        }
      };
    }

    connect();

    return () => {
      unmounted = true;
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [sessionId]);

  return { connectionState };
}
