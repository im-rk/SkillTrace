"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { examAdminApi } from "@/features/exam-admin/api/exam-admin.api";
import type { Skill } from "@/features/question-bank-admin/api/skills.api";
import { LOCAL_TIMEZONE } from "@/lib/timezone";

/** <input type="datetime-local"> has no timezone of its own -- the browser
 * treats the value as the viewer's local time. `new Date(value)` interprets
 * it the same way, so .toISOString() correctly converts to UTC for the
 * backend without the user ever having to think about UTC themselves. */
function localDateTimeToIso(value: string): string {
  return new Date(value).toISOString();
}

export function ExamCreateForm({ skills }: { skills: Skill[] }) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [skillId, setSkillId] = useState(skills[0]?.id ?? "");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const exam = await examAdminApi.create({
        title,
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

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Title
        <input required value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>

      <label>
        Skill
        <select value={skillId} onChange={(e) => setSkillId(e.target.value)} required>
          {skills.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Start time ({LOCAL_TIMEZONE})
        <input type="datetime-local" required value={startTime} onChange={(e) => setStartTime(e.target.value)} />
      </label>

      <label>
        End time ({LOCAL_TIMEZONE})
        <input type="datetime-local" required value={endTime} onChange={(e) => setEndTime(e.target.value)} />
      </label>

      <label>
        Duration (minutes)
        <input
          type="number"
          min={1}
          required
          value={durationMinutes}
          onChange={(e) => setDurationMinutes(Number(e.target.value))}
        />
      </label>

      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={submitting || !skillId}>
        {submitting ? "Creating…" : "Create exam"}
      </button>
    </form>
  );
}
