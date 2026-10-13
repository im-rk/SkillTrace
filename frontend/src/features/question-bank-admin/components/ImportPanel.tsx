"use client";

import { useState, type DragEvent } from "react";
import { ApiError } from "@/lib/api-client";
import { questionBankApi, type BulkImportResponse } from "@/features/question-bank-admin/api/question-bank.api";
import { Notice } from "@/components/ui/Bits";
import { Icon } from "@/components/ui/Icon";

const SAMPLE = `question_type,prompt,difficulty,content,tags
true_false,"Is 1/2 equal to 2/4?",easy,"{""correct_answer"": true}",equivalence
multiple_choice,"What is 1/2 + 1/4?",medium,"{""choices"": [{""id"": ""a"", ""text"": ""3/4""}, {""id"": ""b"", ""text"": ""2/6""}], ""correct_choice_id"": ""a""}",addition
text_input,"What is 3/4 as a decimal?",easy,"{""correct_answer"": ""0.75"", ""case_sensitive"": false}",decimals`;

function Results({ result }: { result: BulkImportResponse }) {
  const failed = result.results.filter((r) => r.status === "failed");
  return (
    <div className="stack-sm">
      <Notice tone={result.failed === 0 ? "ok" : "warn"} role="status">
        {result.succeeded} of {result.total_rows} rows imported
        {result.failed > 0 && `, ${result.failed} failed`}
      </Notice>
      {failed.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <thead>
              <tr>
                <th>Row</th>
                <th>Problem</th>
              </tr>
            </thead>
            <tbody>
              {failed.map((row) => (
                <tr key={row.row_number}>
                  <td className="num">{row.row_number}</td>
                  <td>{row.error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Bulk import: drop a CSV or JSON file; each row is checked on its own and the report says which ones failed. */
export function ImportPanel({ skillId, onImported, onClose }: { skillId: string; onImported: () => void; onClose: () => void }) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkImportResponse | null>(null);
  const [importing, setImporting] = useState(false);

  async function importFile(file: File) {
    setError(null);
    setResult(null);
    setImporting(true);
    try {
      const response = file.name.endsWith(".json")
        ? await questionBankApi.bulkImportJson(skillId, JSON.parse(await file.text()))
        : await questionBankApi.bulkImportCsv(skillId, file);
      setResult(response);
      if (response.succeeded > 0) onImported();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not import this file.");
    } finally {
      setImporting(false);
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) importFile(file);
  }

  return (
    <section className="card" aria-label="Import questions">
      <div className="card-head">
        <div>
          <h2 className="h2">Import questions from a file</h2>
          <p className="muted small">Useful for moving an existing question set in one go.</p>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close import">
          <Icon name="x" />
        </button>
      </div>
      <div className="card-body stack">
        <div
          className="dropzone"
          data-dragging={isDragging}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          <Icon name="upload" />
          <div>{importing ? "Importing…" : "Drop a CSV or JSON file here"}</div>
          <label className="btn btn-secondary btn-sm" style={{ cursor: "pointer" }}>
            Choose file
            <input
              type="file"
              accept=".csv,.json"
              disabled={importing}
              className="sr-only"
              aria-label="Choose a CSV or JSON file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) importFile(file);
              }}
            />
          </label>
        </div>

        {error && <Notice tone="error">{error}</Notice>}
        {result && <Results result={result} />}

        <details className="disclosure">
          <summary>
            <Icon name="info" small />
            What should the file look like?
          </summary>
          <p className="muted small" style={{ marginBottom: 10 }}>
            One row per question with the columns <code>question_type</code>, <code>prompt</code>, <code>difficulty</code>, <code>content</code> (JSON) and optional{" "}
            <code>tags</code>.
          </p>
          <pre className="mono small" style={{ overflowX: "auto", padding: 14, borderRadius: 8, background: "var(--surface-2)" }}>
            {SAMPLE}
          </pre>
        </details>
      </div>
    </section>
  );
}
