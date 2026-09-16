"use client";

import { use, useEffect, useState } from "react";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { resultsApi, type ExamOverview } from "@/features/exam-results/api/results.api";
import { ExamOverviewTable } from "@/features/exam-results/components/ExamOverviewTable";

function ExamOverviewContent({ examId }: { examId: string }) {
  const [overview, setOverview] = useState<ExamOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    resultsApi
      .getOverview(examId)
      .then((loaded) => {
        if (!cancelled) setOverview(loaded);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : "Could not load results.");
      });
    return () => {
      cancelled = true;
    };
  }, [examId]);

  if (error) return <p role="alert">{error}</p>;
  if (!overview) return <p>Loading…</p>;

  return (
    <main>
      <h1>Results overview</h1>
      {overview.results.length === 0 ? (
        <p>No results yet — results appear once students have submitted their exam.</p>
      ) : (
        <ExamOverviewTable examId={examId} rows={overview.results} />
      )}
    </main>
  );
}

export default function ExamOverviewPage({ params }: { params: Promise<{ examId: string }> }) {
  const { examId } = use(params);
  const { user } = useAuth();

  return (
    <RequireAuth>
      {user && user.role !== "student" ? (
        <ExamOverviewContent examId={examId} />
      ) : (
        <p role="alert">Only instructors and admins can view the results overview.</p>
      )}
    </RequireAuth>
  );
}
