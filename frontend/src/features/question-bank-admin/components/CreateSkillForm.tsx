"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api-client";
import { skillsApi } from "@/features/question-bank-admin/api/skills.api";

export function CreateSkillForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const slug = name
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "");
      await skillsApi.create({ name: name.trim(), slug });
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not create this skill.");
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        New skill name
        <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Algebra" />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={!name.trim()}>
        Add skill
      </button>
    </form>
  );
}
