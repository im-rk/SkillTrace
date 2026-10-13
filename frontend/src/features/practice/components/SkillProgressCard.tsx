"use client";

import Link from "next/link";
import { Chip } from "@/components/ui/Chip";
import { Icon } from "@/components/ui/Icon";
import { Meter } from "@/components/ui/Bits";
import { pct } from "@/lib/format";
import type { SkillMastery } from "@/features/practice/api/practice.api";

/** One skill from the student's point of view: where they are, and the next thing to do. */
export function SkillProgressCard({
  skill,
  onStart,
  starting,
}: {
  skill: SkillMastery;
  onStart: (skillId: string) => void;
  starting: boolean;
}) {
  const started = skill.current_mastery !== null;
  const value = skill.current_mastery ?? 0;

  return (
    <article className="card card-pad" data-testid="practice-skill">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div style={{ minWidth: 0, overflowWrap: "anywhere" }}>
          <h3 className="h2">{skill.name}</h3>
          {skill.description && <p className="muted small">{skill.description}</p>}
        </div>
        <span style={{ flex: "none" }}>
          {skill.is_mastered ? <Chip tone="ok">Mastered</Chip> : started ? <Chip tone="brand">In progress</Chip> : <Chip>Not started</Chip>}
        </span>
      </div>

      <div style={{ margin: "20px 0 8px" }}>
        <div className="row-between" style={{ marginBottom: 8 }}>
          <span className="num" style={{ fontSize: 28, fontWeight: 650, letterSpacing: "-0.02em" }}>
            {started ? `${pct(value)}%` : "—"}
          </span>
          <span className="muted small">Goal {pct(skill.mastery_threshold)}%</span>
        </div>
        <Meter value={value} goal={skill.mastery_threshold} label={`${skill.name} mastery`} />
      </div>

      <p className="muted small" style={{ marginBottom: 18 }}>
        {started
          ? `Mastery ${pct(value)}% after ${skill.total_attempts} ${skill.total_attempts === 1 ? "answer" : "answers"}${skill.is_mastered ? " — mastered" : ""}`
          : "Not started"}
        {" · "}
        {skill.question_count} questions
      </p>

      <div className="row">
        {skill.is_mastered ? (
          <span className="chip chip-ok plain">
            <Icon name="check" small /> Skill mastered
          </span>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            disabled={skill.question_count === 0 || starting}
            onClick={() => onStart(skill.skill_id)}
          >
            {skill.total_attempts > 0 ? "Continue practice" : "Start practice"}
          </button>
        )}
        <Link href={`/progress?skill=${skill.skill_id}`} className="btn btn-ghost">
          <Icon name="trend" small />
          Progress
        </Link>
      </div>
    </article>
  );
}
