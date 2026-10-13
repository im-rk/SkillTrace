import type { ConnectionState } from "@/features/exam-taking/hooks/useExamSession";
import { Icon } from "@/components/ui/Icon";

function formatTime(totalSeconds: number): string {
  const clamped = Math.max(totalSeconds, 0);
  const minutes = Math.floor(clamped / 60);
  const seconds = clamped % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function ExamTimer({ secondsLeft, connectionState }: { secondsLeft: number | null; connectionState: ConnectionState }) {
  // A frozen number during a disconnect looks identical to a bug -- label it
  // explicitly rather than letting the countdown silently stop ticking.
  if (connectionState === "reconnecting" || connectionState === "disconnected_final") {
    return (
      <div role="timer">
        <Icon name="clock" /> Paused — reconnecting…
      </div>
    );
  }

  if (secondsLeft === null) {
    return (
      <div role="timer">
        <Icon name="clock" /> Loading…
      </div>
    );
  }

  return (
    <div role="timer" data-low={secondsLeft <= 60}>
      <Icon name="clock" /> {formatTime(secondsLeft)}
    </div>
  );
}
