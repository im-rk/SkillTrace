import Link from "next/link";
import type { StudentExamResult } from "@/features/exam-results/api/results.api";
import { Ring } from "@/components/ui/Bits";
import { pct } from "@/lib/format";

export function StudentResultCard({ result }: { result: StudentExamResult }) {
  const mastery = result.final_mastery;
  return (
    <div className="stack">
      <section className="card card-pad" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "24px 40px" }}>
        <Ring value={mastery ?? 0}>
          <b className="num">{mastery !== null ? `${pct(mastery)}%` : "—"}</b>
          <span className="muted small">mastery</span>
        </Ring>
        <div style={{ flex: 1, minWidth: 240 }}>
          <h2 className="h2">What this exam says about you</h2>
          <p className="muted" style={{ marginTop: 8 }}>
            Your score counts the points you earned. Your <b>mastery</b> is different: it is the system&apos;s estimate of how well you know the skill, built from
            every answer you have given, in practice and in this exam, and it can move your whole level, not just this one result.
          </p>
          <div className="row" style={{ marginTop: 16 }}>
            <Link href="/progress" className="btn btn-secondary btn-sm">
              See how it moved
            </Link>
            <Link href="/practice" className="btn btn-ghost btn-sm">
              Keep practising
            </Link>
          </div>
        </div>
      </section>

      <dl className="grid grid-2" style={{ margin: 0 }}>
        <div className="stat">
          <dt className="label">Total score</dt>
          <dd className="value num">{result.total_score}</dd>
          <div className="sub">Points earned</div>
        </div>
        <div className="stat">
          <dt className="label">Questions answered</dt>
          <dd className="value num">{result.questions_answered}</dd>
          <div className="sub">In this exam</div>
        </div>
      </dl>
    </div>
  );
}
