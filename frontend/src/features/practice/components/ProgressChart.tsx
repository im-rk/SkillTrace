"use client";

import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { pct } from "@/lib/format";
import type { Progress } from "@/features/practice/api/practice.api";

interface ChartPoint {
  answer: number;
  mastery: number;
  before: number | null;
  kind: "start" | "answer";
  correct: boolean | null;
  source: "start" | "practice" | "exam";
  viterbi: boolean;
}

/** Filled dot = correct, cross = incorrect (shape as well as colour), hollow grey = the starting estimate. */
function AnswerDot({ cx, cy, payload }: { cx?: number; cy?: number; payload?: ChartPoint }) {
  if (cx === undefined || cy === undefined || !payload) return null;
  if (payload.kind === "start") {
    return <circle className="answer-dot" data-kind="start" cx={cx} cy={cy} r={5} fill="var(--surface)" stroke="var(--muted)" strokeWidth={2} />;
  }
  if (payload.correct) {
    return <circle className="answer-dot" data-kind="correct" cx={cx} cy={cy} r={5.5} fill="var(--brand)" stroke="var(--surface)" strokeWidth={2} />;
  }
  return (
    <g className="answer-dot" data-kind="incorrect">
      <circle cx={cx} cy={cy} r={8} fill="var(--surface)" />
      <path d={`M${cx - 4} ${cy - 4}L${cx + 4} ${cy + 4}M${cx + 4} ${cy - 4}L${cx - 4} ${cy + 4}`} stroke="var(--rust)" strokeWidth={2.4} strokeLinecap="round" />
    </g>
  );
}

function Readout({ active, payload }: { active?: boolean; payload?: { payload: ChartPoint }[] }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  const change = point.before === null ? null : point.mastery - point.before;
  return (
    <div className="chart-tip">
      <div className="tip-value num">{point.mastery}%</div>
      <div className="tip-label">
        {point.kind === "start"
          ? "Starting estimate"
          : `${point.source === "exam" ? "Exam" : "Practice"} answer ${point.answer} · ${point.correct ? "correct" : "incorrect"}`}
      </div>
      {change !== null && change !== 0 && (
        <div className="tip-label num">
          was {point.before}% ({change > 0 ? "+" : ""}
          {change} points)
        </div>
      )}
      {point.viterbi && <div className="tip-label">Most likely already mastered</div>}
    </div>
  );
}

/** Mastery after each answer, oldest first. Exam and practice answers form one continuous chain. */
export function ProgressChart({ progress }: { progress: Progress }) {
  const data: ChartPoint[] = [
    { answer: 0, mastery: pct(progress.initial_mastery), before: null, kind: "start", correct: null, source: "start", viterbi: false },
    ...progress.points.map((p, i) => ({
      answer: i + 1,
      mastery: pct(p.mastery_after),
      before: pct(p.mastery_before),
      kind: "answer" as const,
      correct: p.is_correct,
      source: p.source,
      viterbi: p.viterbi_mastered,
    })),
  ];
  // The first answer at which the whole-history (Viterbi) reading flips to "mastered" -- a hindsight estimate of
  // when learning most likely happened, different from the running belief crossing the goal.
  const viterbiAt = data.find((d) => d.viterbi)?.answer;
  const goal = pct(progress.mastery_threshold);

  return (
    <div data-testid="progress-chart" style={{ width: "100%", height: 340 }} role="img" aria-label={`Mastery after each of ${progress.points.length} answers, ending at ${data[data.length - 1].mastery} percent`}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 28, right: 28, bottom: 8, left: -8 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" />
          <XAxis dataKey="answer" type="number" domain={[0, "dataMax"]} allowDecimals={false} tickLine={false} axisLine={{ stroke: "var(--line-2)" }} tickMargin={10} />
          <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`} tickLine={false} axisLine={false} width={52} />
          <Tooltip content={<Readout />} cursor={{ stroke: "var(--ink-2)", strokeOpacity: 0.4, strokeWidth: 1 }} isAnimationActive={false} />
          <ReferenceLine y={goal} stroke="var(--amber)" strokeWidth={1.75} strokeDasharray="7 5" label={{ value: `Goal ${goal}%`, position: "insideBottomLeft", fill: "var(--ink-2)", fontSize: 12, fontWeight: 600 }} />
          {viterbiAt !== undefined && (
            <ReferenceLine
              x={viterbiAt}
              stroke="var(--ink-2)"
              strokeOpacity={0.55}
              strokeWidth={1.5}
              label={{ value: "Likely mastered here", position: "top", fill: "var(--ink-2)", fontSize: 12, fontWeight: 600 }}
            />
          )}
          <Area
            type="monotone"
            dataKey="mastery"
            stroke="var(--brand)"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="var(--brand)"
            fillOpacity={0.1}
            dot={<AnswerDot />}
            activeDot={{ r: 7, stroke: "var(--surface)", strokeWidth: 2, fill: "var(--brand)" }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ChartKey() {
  return (
    <div className="chart-key" aria-hidden="true">
      <span>
        <i className="key-dot" /> Correct answer
      </span>
      <span>
        <svg width="12" height="12" viewBox="0 0 12 12">
          <path d="M2 2l8 8M10 2l-8 8" stroke="var(--rust)" strokeWidth="2.2" strokeLinecap="round" />
        </svg>{" "}
        Incorrect answer
      </span>
      <span>
        <i className="key-line" /> Goal
      </span>
      <span>
        <i className="key-line solid" /> Likely mastered here
      </span>
    </div>
  );
}
