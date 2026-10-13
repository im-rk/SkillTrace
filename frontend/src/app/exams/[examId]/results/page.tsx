"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ApiError } from "@/lib/api-client";
import { resultsApi, type StudentExamResult } from "@/features/exam-results/api/results.api";
import { StudentResultCard } from "@/features/exam-results/components/StudentResultCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, LoadingBlock } from "@/components/ui/Bits";

function StudentResultsContent({ examId }: { examId: string }) {
  const [result, setResult] = useState<StudentExamResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    resultsApi
      .getMyResult(examId)
      .then((loaded) => {
        if (!cancelled) setResult(loaded);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setPending(true);
        else setError(err instanceof ApiError ? err.detail : "Could not load your results.");
      });
    return () => {
      cancelled = true;
    };
  }, [examId]);

  return (
    <main className="narrow">
      <PageHeader eyebrow="Exam" title="Your results" crumbs={[{ href: "/dashboard", label: "Dashboard" }, { label: "Results" }]} />
      {error && (
        <p role="alert" className="notice notice-error">
          {error}
        </p>
      )}
      {pending && (
        <div className="card">
          <EmptyState
            icon="clock"
            title="Results aren't available yet"
            action={
              <Link href="/dashboard" className="btn btn-secondary">
                Back to dashboard
              </Link>
            }
          >
            Results appear after your instructor closes the exam. Check back soon.
          </EmptyState>
        </div>
      )}
      {!result && !error && !pending && <LoadingBlock lines={4} />}
      {result && <StudentResultCard result={result} />}
    </main>
  );
}

export default function StudentResultsPage({ params }: { params: Promise<{ examId: string }> }) {
  const { examId } = use(params);
  return (
    <RequireAuth>
      <StudentResultsContent examId={examId} />
    </RequireAuth>
  );
}
