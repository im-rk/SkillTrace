"use client";

import { use, useEffect, useState } from "react";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { ApiError } from "@/lib/api-client";
import { resultsApi, type ExamOverview, type ItemAnalysis } from "@/features/exam-results/api/results.api";
import { examAdminApi, type ExamListItem } from "@/features/exam-admin/api/exam-admin.api";
import { ExamOverviewTable } from "@/features/exam-results/components/ExamOverviewTable";
import { ItemAnalysisTable } from "@/features/exam-results/components/ItemAnalysisTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { PhaseChip } from "@/components/ui/Chip";
import { EmptyState, LoadingBlock, Notice, Stat } from "@/components/ui/Bits";
import { pct } from "@/lib/format";

function ExamOverviewContent({ examId }: { examId: string }) {
  const [exam, setExam] = useState<ExamListItem | null>(null);
  const [overview, setOverview] = useState<ExamOverview | null>(null);
  const [itemAnalysis, setItemAnalysis] = useState<ItemAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([examAdminApi.list(), resultsApi.getOverview(examId), resultsApi.getItemAnalysis(examId)])
      .then(([exams, loadedOverview, loadedItemAnalysis]) => {
        if (cancelled) return;
        setExam(exams.find((e) => e.id === examId) ?? null);
        setOverview(loadedOverview);
        setItemAnalysis(loadedItemAnalysis);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : "Could not load results.");
      });
    return () => {
      cancelled = true;
    };
  }, [examId]);

  if (error)
    return (
      <main className="narrow">
        <Notice tone="error">{error}</Notice>
      </main>
    );
  if (!overview)
    return (
      <main>
        <LoadingBlock lines={5} />
      </main>
    );

  const rows = overview.results;
  const avgScore = rows.length ? rows.reduce((s, r) => s + r.total_score, 0) / rows.length : 0;
  const withMastery = rows.filter((r) => r.final_mastery !== null);
  const avgMastery = withMastery.length ? withMastery.reduce((s, r) => s + (r.final_mastery ?? 0), 0) / withMastery.length : null;
  const weak = (itemAnalysis?.items ?? []).filter((i) => i.discrimination !== null && i.discrimination < 0.2).length;

  return (
    <main>
      <PageHeader
        crumbs={[
          { href: "/admin/exams", label: "Exams" },
          ...(exam ? [{ href: `/admin/exams/${exam.id}`, label: exam.title }] : []),
          { label: "Results" },
        ]}
        eyebrow={exam?.skill_name ?? "Exam"}
        title="Results overview"
        lede={exam ? <span className="row" style={{ gap: 10 }}>{exam.title} <PhaseChip phase={exam.phase} /></span> : undefined}
      />

      {rows.length === 0 ? (
        <div className="card">
          <EmptyState icon="users" title="No results yet">
            Results appear once students have submitted their exam and the exam has been closed.
          </EmptyState>
        </div>
      ) : (
        <div className="stack">
          <div className="grid grid-4">
            <Stat label="Students" value={rows.length} sub="Submitted" />
            <Stat label="Average score" value={avgScore.toFixed(1)} sub="Points per student" />
            <Stat label="Average mastery" value={avgMastery === null ? "—" : `${pct(avgMastery)}%`} sub="Across the class" />
            <Stat label="Questions to review" value={weak} sub="Weak discrimination" />
          </div>

          <section className="card" aria-label="Students">
            <div className="card-head">
              <div>
                <h2 className="h2">Students</h2>
                <p className="muted small">
                  <b>Score</b> adds the points earned in this exam. <b>Mastery</b> is the model&apos;s estimate of the skill, built from all of a student&apos;s answers.
                </p>
              </div>
            </div>
            <ExamOverviewTable examId={examId} rows={rows} />
          </section>

          <section className="card" aria-label="Item analysis">
            <div className="card-head">
              <div>
                <h2 className="h2">Item analysis</h2>
                <p className="muted small">
                  Did each question work? <b>Got it right</b> is the share who answered correctly (difficulty). <b>Discrimination</b> compares the top and bottom 27% of
                  students: a good question is answered right far more often by the top group.
                </p>
              </div>
            </div>
            {itemAnalysis ? <ItemAnalysisTable items={itemAnalysis.items} /> : <div className="card-body"><LoadingBlock /></div>}
          </section>
        </div>
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
        <main className="narrow">
          <Notice tone="error">Only instructors and admins can view the results overview.</Notice>
        </main>
      )}
    </RequireAuth>
  );
}
