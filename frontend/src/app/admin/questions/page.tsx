"use client";

import { useCallback, useEffect, useState } from "react";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { skillsApi, type Skill } from "@/features/question-bank-admin/api/skills.api";
import { questionBankApi, type Question } from "@/features/question-bank-admin/api/question-bank.api";
import { CreateSkillForm } from "@/features/question-bank-admin/components/CreateSkillForm";
import { QuestionForm } from "@/features/question-bank-admin/components/QuestionForm";
import { QuestionList } from "@/features/question-bank-admin/components/QuestionList";
import { BulkImportForm } from "@/features/question-bank-admin/components/BulkImportForm";

function QuestionBankAdminContent() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string>("");
  const [questions, setQuestions] = useState<Question[]>([]);

  const reloadSkills = useCallback(async () => {
    const loaded = await skillsApi.list();
    setSkills(loaded);
    setSelectedSkillId((current) => current || loaded[0]?.id || "");
  }, []);

  // GET /question-bank/questions requires a skill_id or tags filter --
  // there is no "list every question" mode -- so this only ever loads once
  // a skill is selected.
  const reloadQuestions = useCallback(async (skillId: string) => {
    setQuestions(skillId ? await questionBankApi.list(skillId) : []);
  }, []);

  useEffect(() => {
    // Fetch-on-mount; setState happens after an await, not synchronously in the render phase.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reloadSkills();
  }, [reloadSkills]);

  useEffect(() => {
    // Guards against a race when the skill selector changes quickly: an
    // earlier, slower request resolving after a later one would otherwise
    // overwrite the list with the wrong skill's questions.
    let cancelled = false;
    async function load() {
      const loaded = selectedSkillId ? await questionBankApi.list(selectedSkillId) : [];
      if (!cancelled) setQuestions(loaded);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [selectedSkillId]);

  return (
    <main>
      <h1>Question bank</h1>

      <section>
        <h2>Skills</h2>
        <label>
          Viewing skill
          <select value={selectedSkillId} onChange={(e) => setSelectedSkillId(e.target.value)}>
            {skills.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <CreateSkillForm onCreated={reloadSkills} />
      </section>

      <section>
        <h2>Add a question</h2>
        {skills.length === 0 ? (
          <p>Add a skill first.</p>
        ) : (
          <QuestionForm skills={skills} onCreated={() => reloadQuestions(selectedSkillId)} />
        )}
      </section>

      <section>
        <h2>Bulk import</h2>
        {skills.length === 0 ? <p>Add a skill first.</p> : <BulkImportForm skills={skills} />}
      </section>

      <section>
        <h2>Existing questions</h2>
        <QuestionList questions={questions} onDeleted={() => reloadQuestions(selectedSkillId)} />
      </section>
    </main>
  );
}

export default function QuestionBankAdminPage() {
  const { user } = useAuth();

  return (
    <RequireAuth>
      {user && user.role !== "student" ? (
        <QuestionBankAdminContent />
      ) : (
        <p role="alert">Only instructors and admins can manage the question bank.</p>
      )}
    </RequireAuth>
  );
}
