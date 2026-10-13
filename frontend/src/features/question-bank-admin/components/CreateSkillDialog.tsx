"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { skillsApi } from "@/features/question-bank-admin/api/skills.api";
import { Modal } from "@/components/ui/Modal";
import { Notice } from "@/components/ui/Bits";

const slugify = (name: string) =>
  name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

/** Creates a skill, then opens it so the next thing the instructor does is add its questions. */
export function CreateSkillDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const skill = await skillsApi.create({ name: name.trim(), slug: slugify(name), description: description.trim() || undefined });
      setName("");
      setDescription("");
      onClose();
      router.push(`/admin/skills/${skill.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not create this skill.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New skill"
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="create-skill-form" className="btn btn-primary" disabled={saving || !name.trim()}>
            {saving ? "Creating…" : "Create skill"}
          </button>
        </>
      }
    >
      <form id="create-skill-form" onSubmit={handleSubmit} className="stack-sm">
        <p className="muted">
          A skill is one topic you want students to master, for example <i>Fractions</i> or <i>Newton&apos;s laws</i>. You will add its questions next.
        </p>
        <div className="field">
          <label htmlFor="skill-name">Skill name</label>
          <input id="skill-name" className="input" required autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Fractions" />
        </div>
        <div className="field">
          <label htmlFor="skill-description">Description (optional)</label>
          <input
            id="skill-description"
            className="input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What students will be able to do"
          />
          <span className="hint">Students see this next to the skill.</span>
        </div>
        {error && <Notice tone="error">{error}</Notice>}
      </form>
    </Modal>
  );
}
