"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { enrollmentApi } from "@/features/enrollment/api/enrollment.api";

export function RedeemCodeForm() {
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
      // The backend already returns a specific, user-facing message for each
      // failure mode (invalid / expired / usage-limit-reached) -- surface it
      // directly rather than re-deriving a generic one from the status code.
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Access code
        <input required value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. ABCD-1234" />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={submitting || !code.trim()}>
        {submitting ? "Redeeming…" : "Join exam"}
      </button>
    </form>
  );
}
