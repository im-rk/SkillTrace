"use client";

import { Suspense } from "react";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ExamCreateForm } from "@/features/exam-admin/components/ExamCreateForm";
import { PageHeader } from "@/components/ui/PageHeader";
import { LoadingBlock, Notice } from "@/components/ui/Bits";

export default function NewExamPage() {
  const { user } = useAuth();
  return (
    <RequireAuth>
      <main className="narrow">
        {user && user.role !== "student" ? (
          <>
            <PageHeader
              crumbs={[{ href: "/admin/exams", label: "Exams" }, { label: "New exam" }]}
              eyebrow="Exams"
              title="New exam"
              lede="Choose what it tests and when students can take it. You will pick the questions next."
            />
            <Suspense fallback={<LoadingBlock lines={5} />}>
              <ExamCreateForm />
            </Suspense>
          </>
        ) : (
          <Notice tone="error">Only instructors and admins can manage exams.</Notice>
        )}
      </main>
    </RequireAuth>
  );
}
