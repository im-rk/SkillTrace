"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { skillsApi, type Skill, type SkillReadiness } from "@/features/question-bank-admin/api/skills.api";
import { Chip } from "@/components/ui/Chip";
import { Icon } from "@/components/ui/Icon";

/** A skill in the instructor's list: how complete its question bank is, and how students are doing. */
export function SkillCard({ skill }: { skill: Skill }) {
  const [readiness, setReadiness] = useState<SkillReadiness | null>(null);
  const [students, setStudents] = useState<{ total: number; mastered: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([skillsApi.readiness(skill.id), skillsApi.overview(skill.id)]).then(([r, o]) => {
      if (cancelled) return;
      setReadiness(r);
      setStudents({ total: o.length, mastered: o.filter((row) => row.is_mastered).length });
    });
    return () => {
      cancelled = true;
    };
  }, [skill.id]);

  const total = readiness ? readiness.counts.easy + readiness.counts.medium + readiness.counts.hard : 0;

  return (
    <Link href={`/admin/skills/${skill.id}`} className="card card-pad card-link" data-testid="skill-card">
      <div className="row-between" style={{ alignItems: "flex-start" }}>
        <div>
          <h2 className="h2">{skill.name}</h2>
          <p className="muted small" style={{ minHeight: 20 }}>
            {skill.description ?? "No description"}
          </p>
        </div>
        {readiness && (readiness.ready ? <Chip tone="ok">Ready</Chip> : <Chip tone="warn">Needs questions</Chip>)}
      </div>

      <div className="tiers" style={{ margin: "18px 0" }} aria-label="Questions by difficulty">
        {(["easy", "medium", "hard"] as const).map((tier) => (
          <div key={tier} className={`tier ${readiness && readiness.counts[tier] === 0 ? "empty-tier" : ""}`}>
            <b className="num">{readiness ? readiness.counts[tier] : "–"}</b>
            <span style={{ textTransform: "capitalize" }}>{tier}</span>
          </div>
        ))}
      </div>

      <div className="row-between muted small">
        <span>
          <Icon name="book" small /> {total} {total === 1 ? "question" : "questions"}
        </span>
        <span>
          <Icon name="users" small /> {students ? `${students.total} practising · ${students.mastered} mastered` : "…"}
        </span>
      </div>
    </Link>
  );
}
