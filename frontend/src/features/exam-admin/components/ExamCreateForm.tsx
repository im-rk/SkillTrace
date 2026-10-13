"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { examAdminApi } from "@/features/exam-admin/api/exam-admin.api";
import { skillsApi, type Skill, type SkillReadiness } from "@/features/question-bank-admin/api/skills.api";
import { LOCAL_TIMEZONE } from "@/lib/timezone";
import { EmptyState, LoadingBlock, Notice } from "@/components/ui/Bits";

/** `<input type="datetime-local">` has no timezone of its own: the browser treats the value as the viewer's local
 * time, and `new Date(value)` reads it the same way, so `.toISOString()` converts to UTC for the backend. */
const localDateTimeToIso = (value: string) => new Date(value).toISOString();

function toInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

const DURATIONS = [15, 30, 45, 60, 90];

/** Step 1 of an exam: what it tests and when. Questions and the access code come on the next screen. */
export function ExamCreateForm() {
  const router = useRouter();
  const presetSkill = useSearchParams().get("skill");
  const [skills, setSkills] = useState<{ skill: Skill; readiness: SkillReadiness }[] | null>(null);
  const [title, setTitle] = useState("");
  const [skillId, setSkillId] = useState(presetSkill ?? "");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    skillsApi.list().then(async (list) => {
      const withReadiness = await Promise.all(list.map(async (skill) => ({ skill, readiness: await skillsApi.readiness(skill.id) })));
      if (cancelled) return;
      setSkills(withReadiness);
      setSkillId((current) => (withReadiness.some((s) => s.skill.id === current) ? current : (withReadiness.find((s) => s.readiness.ready) ?? withReadiness[0])?.skill.id ?? ""));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  function openFor(hours: number, startsInMinutes = 0) {
    const start = new Date(Date.now() + startsInMinutes * 60_000 - (startsInMinutes === 0 ? 60_000 : 0));
    setStartTime(toInputValue(start));
    setEndTime(toInputValue(new Date(start.getTime() + hours * 3_600_000)));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const exam = await examAdminApi.create({
        title: title.trim(),
        skill_id: skillId,
        start_time: localDateTimeToIso(startTime),
        end_time: localDateTimeToIso(endTime),
        duration_minutes: durationMinutes,
      });
      router.push(`/admin/exams/${exam.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not create the exam.");
    } finally {
      setSubmitting(false);
    }
  }

  if (skills === null) return <LoadingBlock lines={5} />;
  if (skills.length === 0)
    return (
      <div className="card">
        <EmptyState
          icon="book"
          title="Create a skill first"
          action={
            <Link href="/admin/skills?new=1" className="btn btn-primary">
              Create a skill
            </Link>
          }
        >
          An exam tests one skill, so it needs a skill with questions.
        </EmptyState>
      </div>
    );

  const chosen = skills.find((s) => s.skill.id === skillId);
  const windowOk = startTime && endTime && new Date(endTime) > new Date(startTime);

  return (
    <form onSubmit={handleSubmit} className="card card-pad stack">
      <div className="form-grid">
        <div className="field full">
          <label htmlFor="exam-title">Title</label>
          <input id="exam-title" className="input" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Fractions midterm" />
        </div>

        <div className="field full">
          <label htmlFor="exam-skill">Skill</label>
          <select id="exam-skill" className="select" required value={skillId} onChange={(e) => setSkillId(e.target.value)}>
            {skills.map(({ skill, readiness }) => (
              <option key={skill.id} value={skill.id}>
                {skill.name} — {readiness.counts.easy + readiness.counts.medium + readiness.counts.hard} questions
              </option>
            ))}
          </select>
          <span className="hint">Every answer in this exam updates each student&apos;s mastery of this skill.</span>
          {chosen && chosen.readiness.counts.easy + chosen.readiness.counts.medium + chosen.readiness.counts.hard === 0 && (
            <Notice tone="warn">
              This skill has no questions yet.{" "}
              <Link href={`/admin/skills/${chosen.skill.id}`} className="link">
                Add some first
              </Link>
              , then pick them for this exam.
            </Notice>
          )}
        </div>
      </div>

      <div>
        <h2 className="h2">When can students take it?</h2>
        <p className="muted small" style={{ margin: "4px 0 14px" }}>
          The <b>window</b> is when students may start. The <b>duration</b> is how long each student has once they begin.
        </p>
        <div className="row" style={{ marginBottom: 14 }}>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => openFor(3)}>
            Open now for 3 hours
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => openFor(3, 60)}>
            Starts in 1 hour, open 3 hours
          </button>
        </div>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="exam-start">Start time ({LOCAL_TIMEZONE})</label>
            <input id="exam-start" className="input" type="datetime-local" required value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="exam-end">End time ({LOCAL_TIMEZONE})</label>
            <input id="exam-end" className="input" type="datetime-local" required value={endTime} onChange={(e) => setEndTime(e.target.value)} />
            {startTime && endTime && !windowOk && <span className="hint" style={{ color: "var(--rust)" }}>The end must be after the start.</span>}
          </div>
          <div className="field full">
            <label htmlFor="exam-duration">Duration (minutes)</label>
            <div className="row">
              <input
                id="exam-duration"
                className="input num"
                type="number"
                min={1}
                required
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                style={{ width: 110 }}
              />
              <div className="segmented" role="group" aria-label="Common durations">
                {DURATIONS.map((d) => (
                  <button key={d} type="button" aria-pressed={durationMinutes === d} onClick={() => setDurationMinutes(d)}>
                    {d}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {error && <Notice tone="error">{error}</Notice>}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary btn-lg" disabled={submitting || !skillId || !windowOk}>
          {submitting ? "Creating…" : "Create exam"}
        </button>
        <span className="muted small">Next you will choose the questions and get an access code.</span>
      </div>
    </form>
  );
}
