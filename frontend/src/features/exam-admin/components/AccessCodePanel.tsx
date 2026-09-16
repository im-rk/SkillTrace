"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { examAdminApi, type AccessCode } from "@/features/exam-admin/api/exam-admin.api";

export function AccessCodePanel({ examId }: { examId: string }) {
  const [codes, setCodes] = useState<AccessCode[]>([]);
  const [maxUses, setMaxUses] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const mountedRef = useRef(true);

  const reload = useCallback(async () => {
    const loaded = await examAdminApi.listAccessCodes(examId);
    if (mountedRef.current) setCodes(loaded);
  }, [examId]);

  useEffect(() => {
    mountedRef.current = true;
    reload();
    return () => {
      mountedRef.current = false;
    };
  }, [reload]);

  async function handleGenerate() {
    setError(null);
    setGenerating(true);
    try {
      await examAdminApi.createAccessCode(examId, maxUses ? { max_uses: Number(maxUses) } : {});
      if (mountedRef.current) setMaxUses("");
      await reload();
    } catch (err) {
      if (mountedRef.current) setError(err instanceof ApiError ? err.detail : "Could not generate an access code.");
    } finally {
      if (mountedRef.current) setGenerating(false);
    }
  }

  return (
    <div>
      <label>
        Max uses (optional)
        <input type="number" min={1} value={maxUses} onChange={(e) => setMaxUses(e.target.value)} />
      </label>
      <button type="button" disabled={generating} onClick={handleGenerate}>
        {generating ? "Generating…" : "Generate access code"}
      </button>
      {error && <p role="alert">{error}</p>}

      {codes.length === 0 ? (
        <p>No access codes yet.</p>
      ) : (
        <ul>
          {codes.map((c) => (
            <li key={c.code}>
              <code>{c.code}</code> — used {c.times_used}
              {c.max_uses !== null ? ` / ${c.max_uses}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
