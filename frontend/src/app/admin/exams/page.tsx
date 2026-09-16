"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { skillsApi, type Skill } from "@/features/question-bank-admin/api/skills.api";
import { examAdminApi, type Exam } from "@/features/exam-admin/api/exam-admin.api";
import { ExamCreateForm } from "@/features/exam-admin/components/ExamCreateForm";
import { ExamTimeDisplay } from "@/features/exam-admin/components/ExamTimeDisplay";

function ExamAdminContent() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [loadedSkills, loadedExams] = await Promise.all([skillsApi.list(), examAdminApi.list()]);
      if (cancelled) return;
      setSkills(loadedSkills);
      setExams(loadedExams);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main>
      <h1>Exams</h1>

      <section>
        <h2>Create an exam</h2>
        {skills.length === 0 ? (
          <p>
            No skills yet — add one on the <Link href="/admin/questions">question bank</Link> page first.
          </p>
        ) : (
          <ExamCreateForm skills={skills} />
        )}
      </section>

      <section>
        <h2>All exams</h2>
        {exams.length === 0 ? (
          <p>No exams yet.</p>
        ) : (
          <ul>
            {exams.map((exam) => (
              <li key={exam.id}>
                <Link href={`/admin/exams/${exam.id}`}>{exam.title}</Link> ({exam.status}) —{" "}
                <ExamTimeDisplay iso={exam.start_time} /> to <ExamTimeDisplay iso={exam.end_time} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

export default function ExamAdminPage() {
  const { user } = useAuth();

  return (
    <RequireAuth>
      {user && user.role !== "student" ? (
        <ExamAdminContent />
      ) : (
        <p role="alert">Only instructors and admins can manage exams.</p>
      )}
    </RequireAuth>
  );
}
