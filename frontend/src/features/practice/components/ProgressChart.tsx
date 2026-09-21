"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { pct, type Progress } from "@/features/practice/api/practice.api";

/** Mastery after each answer, oldest first. Exam answers and practice answers are one continuous chain. */
export function ProgressChart({ progress }: { progress: Progress }) {
  const data = [
    { answer: 0, mastery: pct(progress.initial_mastery), label: "Start", source: "start", is_correct: null as boolean | null },
    ...progress.points.map((p, i) => ({
      answer: i + 1,
      mastery: pct(p.mastery_after),
      label: new Date(p.answered_at).toLocaleString(),
      source: p.source,
      is_correct: p.is_correct as boolean | null,
    })),
  ];

  return (
    <div data-testid="progress-chart" style={{ width: "100%", maxWidth: 720, height: 320 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 24, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="answer" label={{ value: "Answers", position: "insideBottom", offset: -12 }} />
          <YAxis domain={[0, 100]} unit="%" />
          <Tooltip
            formatter={(value) => [`${value}%`, "Mastery"]}
            labelFormatter={(_, payload) => {
              const p = payload?.[0]?.payload;
              if (!p || p.source === "start") return "Starting estimate";
              return `${p.source === "exam" ? "Exam" : "Practice"} answer #${p.answer} — ${p.is_correct ? "correct" : "incorrect"}`;
            }}
          />
          <ReferenceLine y={pct(progress.mastery_threshold)} stroke="#16a34a" strokeDasharray="6 3" label="Goal" />
          <Line type="monotone" dataKey="mastery" stroke="#2563eb" strokeWidth={2} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
