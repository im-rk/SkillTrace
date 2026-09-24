"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { pct, type Progress } from "@/features/practice/api/practice.api";

/** Mastery after each answer, oldest first. Exam answers and practice answers are one continuous chain. */
export function ProgressChart({ progress }: { progress: Progress }) {
  const data = [
    {
      answer: 0,
      mastery: pct(progress.initial_mastery),
      label: "Start",
      source: "start",
      is_correct: null as boolean | null,
      viterbi_mastered: false,
    },
    ...progress.points.map((p, i) => ({
      answer: i + 1,
      mastery: pct(p.mastery_after),
      label: new Date(p.answered_at).toLocaleString(),
      source: p.source,
      is_correct: p.is_correct as boolean | null,
      viterbi_mastered: p.viterbi_mastered,
    })),
  ];
  // First point where the most-likely-trajectory (Viterbi) call flips to mastered --
  // distinct from the continuous mastery_after line crossing the goal, this is a
  // hindsight-informed "this is most likely when it actually happened" read of the
  // whole sequence at once (see backend/app/modules/quiz_engine/domain/bkt/viterbi.py).
  const viterbiMasteredAt = data.find((d) => d.viterbi_mastered)?.answer;

  return (
    <div data-testid="progress-chart" style={{ width: "100%", maxWidth: 720, height: 320 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 30, right: 24, bottom: 24, left: 0 }}>
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
          {viterbiMasteredAt !== undefined && (
            <ReferenceLine
              x={viterbiMasteredAt}
              stroke="#9333ea"
              strokeDasharray="2 4"
              label={{ value: "Likely mastered here", position: "top", fill: "#9333ea", fontSize: 11 }}
            />
          )}
          <Line type="monotone" dataKey="mastery" stroke="#2563eb" strokeWidth={2} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
