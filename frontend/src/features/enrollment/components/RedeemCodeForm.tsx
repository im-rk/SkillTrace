"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { enrollmentApi } from "@/features/enrollment/api/enrollment.api";
import { Notice } from "@/components/ui/Bits";

export function RedeemCodeForm({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await enrollmentApi.redeemAccessCode(code.trim());
      router.push(`/exams/${result.exam_id}`);
    } catch (err) {
      // The backend already returns a specific, user-facing message for each failure
      // mode (invalid / expired / usage limit reached) -- show it as is.
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="stack-sm">
      <div className="field">
        <label htmlFor="access-code">Access code</label>
        <input
          id="access-code"
          className="input"
          required
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="e.g. 434641"
          style={compact ? undefined : { fontSize: 22, letterSpacing: "0.12em", minHeight: 52 }}
        />
        {!compact && <span className="hint">Your instructor gives you this code. You only need it once; the exam stays on your dashboard.</span>}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      <button type="submit" className={`btn btn-primary ${compact ? "" : "btn-lg"} btn-block`} disabled={submitting || !code.trim()}>
        {submitting ? "Joining…" : "Join exam"}
      </button>
    </form>
  );
}
