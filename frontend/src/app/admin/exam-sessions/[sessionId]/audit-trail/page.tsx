"use client";

import { use, useEffect, useState } from "react";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { resultsApi, type AuditTrail } from "@/features/exam-results/api/results.api";
import { AuditTrailViewer } from "@/features/exam-results/components/AuditTrailViewer";
import { PageHeader } from "@/components/ui/PageHeader";
import { LoadingBlock, Notice } from "@/components/ui/Bits";

function AuditTrailContent({ sessionId }: { sessionId: string }) {
  const [trail, setTrail] = useState<AuditTrail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    resultsApi
      .getAuditTrail(sessionId)
      .then((loaded) => {
        if (!cancelled) setTrail(loaded);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : "Could not load the audit trail.");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <main className="narrow">
      <PageHeader
        eyebrow="Exam session"
        title="Audit trail"
        lede="Everything recorded during this student's attempt: when they started, each answer they submitted, any lost connection, and how it ended."
      />
      {error && <Notice tone="error">{error}</Notice>}
      {!trail && !error && <LoadingBlock lines={4} />}
      {trail && <AuditTrailViewer events={trail.events} />}
    </main>
  );
}

export default function AuditTrailPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const { user } = useAuth();

  return (
    <RequireAuth>
      {user && user.role !== "student" ? (
        <AuditTrailContent sessionId={sessionId} />
      ) : (
        <main className="narrow">
          <Notice tone="error">Only instructors and admins can view the audit trail.</Notice>
        </main>
      )}
    </RequireAuth>
  );
}
