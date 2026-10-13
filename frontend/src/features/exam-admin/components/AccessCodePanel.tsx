"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { examAdminApi, type AccessCode } from "@/features/exam-admin/api/exam-admin.api";
import { CopyButton, Notice } from "@/components/ui/Bits";

/** The code students type under Join exam. The newest code is shown large so it can be read out or put on a slide. */
export function AccessCodePanel({ examId, onChanged }: { examId: string; onChanged: (count: number) => void }) {
  const [codes, setCodes] = useState<AccessCode[] | null>(null);
  const [maxUses, setMaxUses] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const mountedRef = useRef(true);

  const reload = useCallback(async () => {
    const loaded = await examAdminApi.listAccessCodes(examId);
    if (mountedRef.current) {
      setCodes(loaded);
      onChanged(loaded.length);
    }
  }, [examId, onChanged]);

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

  const newest = codes && codes.length > 0 ? codes[codes.length - 1] : null;

  return (
    <div className="stack-sm">
      {newest ? (
        <div className="code-display">
          <code aria-label="Access code">{newest.code}</code>
          <CopyButton text={newest.code} />
        </div>
      ) : (
        <p className="muted small">No code yet. Generate one and share it with your students.</p>
      )}
      {newest && (
        <p className="muted small">
          Used {newest.times_used}
          {newest.max_uses !== null ? ` of ${newest.max_uses}` : ""} {newest.times_used === 1 ? "time" : "times"}. Students enter it under <b>Join exam</b>.
        </p>
      )}

      {codes && codes.length > 1 && (
        <details className="disclosure">
          <summary>All {codes.length} codes</summary>
          <ul style={{ listStyle: "none" }} className="stack-sm">
            {codes.map((c) => (
              <li key={c.code} className="row-between small">
                <code>{c.code}</code>
                <span className="muted">
                  used {c.times_used}
                  {c.max_uses !== null ? ` / ${c.max_uses}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field" style={{ width: 130 }}>
          <label htmlFor="max-uses">Max uses</label>
          <input id="max-uses" className="input" type="number" min={1} placeholder="Unlimited" value={maxUses} onChange={(e) => setMaxUses(e.target.value)} />
        </div>
        <button type="button" className="btn btn-secondary" disabled={generating} onClick={handleGenerate}>
          {generating ? "Generating…" : "Generate access code"}
        </button>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
    </div>
  );
}
