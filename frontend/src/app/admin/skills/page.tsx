"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import {
  skillsApi,
  type Skill,
  type SkillReadiness,
  type StudentMasteryRow,
} from "@/features/question-bank-admin/api/skills.api";
import { pct } from "@/features/practice/api/practice.api";

const PARAMS = [
  ["p_l0", "Initial knowledge P(L0)"],
  ["p_t", "Learning rate P(T)"],
  ["p_g", "Guess P(G)"],
  ["p_s", "Slip P(S)"],
  ["mastery_threshold", "Mastery threshold"],
] as const;

function SkillEditor({ skill, onChanged, onDeleted }: { skill: Skill; onChanged: () => void; onDeleted: () => void }) {
  const [name, setName] = useState(skill.name);
  const [description, setDescription] = useState(skill.description ?? "");
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(PARAMS.map(([k]) => [k, String(skill[k])])));
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await skillsApi.update(skill.id, {
        name: name.trim(),
        description: description.trim() || null,
        ...Object.fromEntries(PARAMS.map(([k]) => [k, Number(values[k])])),
      });
      setMessage("Skill saved.");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not save this skill.");
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${skill.name}"? Existing questions, exams and history are kept.`)) return;
    try {
      await skillsApi.remove(skill.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not delete this skill.");
    }
  }

  return (
    <form onSubmit={save}>
      <label>
        Name
        <input required value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Description
        <input value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      {PARAMS.map(([key, label]) => (
        <label key={key} style={{ display: "block" }}>
          {label}
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            required
            value={values[key]}
            onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
          />
        </label>
      ))}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <button type="submit">Save skill</button>{" "}
      <button type="button" onClick={remove}>
        Delete skill
      </button>
    </form>
  );
}

function Readiness({ readiness }: { readiness: SkillReadiness }) {
  return (
    <div>
      <p>
        Questions: {readiness.counts.easy} easy, {readiness.counts.medium} medium, {readiness.counts.hard} hard.
      </p>
      {!readiness.ready && (
        <p role="alert">
          Not ready for adaptive practice: no {readiness.missing_tiers.join(" or ")} questions. Add some in the{" "}
          <Link href="/admin/questions">question bank</Link>.
        </p>
      )}
    </div>
  );
}

function SkillsAdminContent() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillId, setSkillId] = useState("");
  const [readiness, setReadiness] = useState<SkillReadiness | null>(null);
  const [overview, setOverview] = useState<StudentMasteryRow[] | null>(null);
  const [version, setVersion] = useState(0);

  const reload = useCallback(async () => {
    const loaded = await skillsApi.list();
    setSkills(loaded);
    setSkillId((current) => (loaded.some((s) => s.id === current) ? current : loaded[0]?.id ?? ""));
    setVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount; setState happens after an await
    reload();
  }, [reload]);

  useEffect(() => {
    if (!skillId) return;
    let cancelled = false;
    Promise.all([skillsApi.readiness(skillId), skillsApi.overview(skillId)]).then(([r, o]) => {
      if (cancelled) return;
      setReadiness(r);
      setOverview(o);
    });
    return () => {
      cancelled = true;
    };
  }, [skillId, version]);

  const skill = skills.find((s) => s.id === skillId);

  return (
    <main>
      <h1>Skills</h1>
      {skills.length === 0 ? (
        <p>
          No skills yet. Create one in the <Link href="/admin/questions">question bank</Link>.
        </p>
      ) : (
        <label>
          Skill
          <select value={skillId} onChange={(e) => setSkillId(e.target.value)}>
            {skills.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {skill && (
        <>
          <section>
            <h2>Readiness</h2>
            {readiness && readiness.skill_id === skillId ? <Readiness readiness={readiness} /> : <p>Loading…</p>}
          </section>
          <section>
            <h2>Settings</h2>
            {/* keyed so the form re-initialises when another skill is selected */}
            <SkillEditor key={skill.id} skill={skill} onChanged={reload} onDeleted={reload} />
          </section>
          <section>
            <h2>Student mastery</h2>
            {overview === null ? (
              <p>Loading…</p>
            ) : overview.length === 0 ? (
              <p>No student has attempted this skill yet.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Mastery</th>
                    <th>Answers</th>
                    <th>Mastered</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.map((row) => (
                    <tr key={row.student_id}>
                      <td>{row.display_name}</td>
                      <td>{pct(row.current_mastery)}%</td>
                      <td>{row.total_attempts}</td>
                      <td>{row.is_mastered ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
      <p>
        <Link href="/dashboard">Back to dashboard</Link>
      </p>
    </main>
  );
}

export default function SkillsAdminPage() {
  const { user } = useAuth();
  return (
    <RequireAuth>
      {user && user.role !== "student" ? <SkillsAdminContent /> : <p role="alert">Only instructors and admins can manage skills.</p>}
    </RequireAuth>
  );
}
