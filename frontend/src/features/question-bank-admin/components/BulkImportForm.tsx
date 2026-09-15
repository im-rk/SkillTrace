"use client";

import { useState, type DragEvent } from "react";
import { ApiError } from "@/lib/api-client";
import { questionBankApi, type BulkImportResponse } from "@/features/question-bank-admin/api/question-bank.api";
import { BulkImportResults } from "@/features/question-bank-admin/components/BulkImportResults";
import type { Skill } from "@/features/question-bank-admin/api/skills.api";

export function BulkImportForm({ skills }: { skills: Skill[] }) {
  const [skillId, setSkillId] = useState(skills[0]?.id ?? "");
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkImportResponse | null>(null);
  const [importing, setImporting] = useState(false);

  async function importFile(file: File) {
    setError(null);
    setResult(null);
    setImporting(true);
    try {
      let response: BulkImportResponse;
      if (file.name.endsWith(".json")) {
        const rows = JSON.parse(await file.text());
        response = await questionBankApi.bulkImportJson(skillId, rows);
      } else {
        response = await questionBankApi.bulkImportCsv(skillId, file);
      }
      setResult(response);
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
    <div>
      <label>
        Skill
        <select value={skillId} onChange={(e) => setSkillId(e.target.value)}>
          {skills.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        aria-label="Drop a CSV or JSON file here to bulk import questions"
        data-dragging={isDragging}
      >
        {importing ? "Importing…" : "Drag a CSV or JSON file here, or"}
        <input
          type="file"
          accept=".csv,.json"
          disabled={importing}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) importFile(file);
          }}
        />
      </div>

      {error && <p role="alert">{error}</p>}
      {result && <BulkImportResults result={result} />}
    </div>
  );
}
