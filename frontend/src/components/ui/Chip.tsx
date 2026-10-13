import type { ReactNode } from "react";

export type ChipTone = "neutral" | "ok" | "warn" | "bad" | "info" | "brand";

const TONE: Record<ChipTone, string> = {
  neutral: "",
  ok: "chip-ok",
  warn: "chip-warn",
  bad: "chip-bad",
  info: "chip-info",
  brand: "chip-brand",
};

export function Chip({ tone = "neutral", dot = true, children }: { tone?: ChipTone; dot?: boolean; children: ReactNode }) {
  return <span className={`chip ${TONE[tone]} ${dot ? "" : "plain"}`}>{children}</span>;
}

export const DIFFICULTY_TONE: Record<string, ChipTone> = { easy: "ok", medium: "warn", hard: "bad" };

export function DifficultyChip({ difficulty }: { difficulty: string }) {
  return (
    <Chip tone={DIFFICULTY_TONE[difficulty] ?? "neutral"}>
      <span style={{ textTransform: "capitalize" }}>{difficulty}</span>
    </Chip>
  );
}

const TYPE_LABEL: Record<string, string> = { multiple_choice: "Multiple choice", true_false: "True / false", text_input: "Short answer" };
export const typeLabel = (type: string) => TYPE_LABEL[type] ?? type;

const PHASE: Record<string, { tone: ChipTone; label: string }> = {
  live: { tone: "ok", label: "Live now" },
  upcoming: { tone: "info", label: "Upcoming" },
  ended: { tone: "warn", label: "Ended" },
  closed: { tone: "neutral", label: "Closed" },
};

export function PhaseChip({ phase }: { phase: string }) {
  const { tone, label } = PHASE[phase] ?? { tone: "neutral" as ChipTone, label: phase };
  return <Chip tone={tone}>{label}</Chip>;
}
