"use client";

import { useEffect, useState } from "react";
import { examAdminApi, type EnrolledStudent } from "@/features/exam-admin/api/exam-admin.api";
import { EmptyState } from "@/components/ui/Bits";
import { initials } from "@/lib/format";

export function EnrollmentRoster({ examId, onLoaded }: { examId: string; onLoaded?: (count: number) => void }) {
  const [students, setStudents] = useState<EnrolledStudent[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    examAdminApi.listEnrollments(examId).then((loaded) => {
      if (cancelled) return;
      setStudents(loaded);
      onLoaded?.(loaded.length);
    });
    return () => {
      cancelled = true;
    };
  }, [examId, onLoaded]);

  if (students === null) return null;
  if (students.length === 0)
    return (
      <EmptyState icon="users" title="Nobody has joined yet">
        Students appear here after they enter the access code.
      </EmptyState>
    );

  return (
    <ul className="divided" style={{ listStyle: "none" }}>
      {students.map((s) => (
        <li key={s.student_id} className="row" style={{ padding: "12px 24px", gap: 12 }}>
          <span className="avatar" aria-hidden="true">
            {initials(s.display_name)}
          </span>
          <div>
            <div style={{ fontWeight: 600 }}>{s.display_name}</div>
            <div className="muted small">{s.email}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}
