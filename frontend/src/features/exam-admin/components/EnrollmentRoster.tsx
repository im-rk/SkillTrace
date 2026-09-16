"use client";

import { useEffect, useState } from "react";
import { examAdminApi, type EnrolledStudent } from "@/features/exam-admin/api/exam-admin.api";

export function EnrollmentRoster({ examId }: { examId: string }) {
  const [students, setStudents] = useState<EnrolledStudent[]>([]);

  useEffect(() => {
    let cancelled = false;
    examAdminApi.listEnrollments(examId).then((loaded) => {
      if (!cancelled) setStudents(loaded);
    });
    return () => {
      cancelled = true;
    };
  }, [examId]);

  if (students.length === 0) return <p>No students enrolled yet.</p>;

  return (
    <ul>
      {students.map((s) => (
        <li key={s.student_id}>
          {s.display_name} ({s.email})
        </li>
      ))}
    </ul>
  );
}
