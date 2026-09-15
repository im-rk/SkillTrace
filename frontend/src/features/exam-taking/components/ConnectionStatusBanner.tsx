import type { ConnectionState } from "@/features/exam-taking/hooks/useExamSession";

const MESSAGES: Record<Exclude<ConnectionState, "connected">, string> = {
  connecting: "Connecting…",
  reconnecting: "Connection lost — attempting to reconnect…",
  disconnected_final: "Connection lost. Please refresh the page to continue your exam.",
};

/**
 * A silent freeze is the worst possible failure mode here -- from the
 * student's perspective it's indistinguishable from the app being broken.
 * Renders nothing only when the connection is actually healthy.
 */
export function ConnectionStatusBanner({ connectionState }: { connectionState: ConnectionState }) {
  if (connectionState === "connected") return null;
  return <div role="status">{MESSAGES[connectionState]}</div>;
}
