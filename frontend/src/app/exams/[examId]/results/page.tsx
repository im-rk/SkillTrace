"use client";

import { use, useEffect, useState } from "react";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { ApiError } from "@/lib/api-client";
import { resultsApi, type StudentExamResult } from "@/features/exam-results/api/results.api";
import { StudentResultCard } from "@/features/exam-results/components/StudentResultCard";

function StudentResultsContent({ examId }: { examId: string }) {
  const [result, setResult] = useState<StudentExamResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    resultsApi
      .getMyResult(examId)
      .then((loaded) => {
        if (!cancelled) setResult(loaded);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError && err.status === 404
              ? "Results aren't available yet for this exam."
              : err instanceof ApiError
                ? err.detail
                : "Could not load your results.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [examId]);

  if (error) return <p role="alert">{error}</p>;
  if (!result) return <p>Loading…</p>;

  return (
    <main>
      <h1>Your results</h1>
      <StudentResultCard result={result} />
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
