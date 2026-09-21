import { api } from "@/lib/api-client";

export interface Skill {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  p_l0: number;
  p_t: number;
  p_g: number;
  p_s: number;
  mastery_threshold: number;
}

export interface SkillCreate {
  name: string;
  slug: string;
  description?: string;
}

export type SkillUpdate = Partial<Omit<Skill, "id" | "slug">>;

export interface SkillReadiness {
  skill_id: string;
  counts: Record<"easy" | "medium" | "hard", number>;
  ready: boolean;
  missing_tiers: string[];
}

export interface StudentMasteryRow {
  student_id: string;
  display_name: string;
  email: string;
  current_mastery: number;
  total_attempts: number;
  is_mastered: boolean;
  last_updated_at: string;
}

export const skillsApi = {
  list: () => api.get<Skill[]>("/skills"),
  create: (data: SkillCreate) => api.post<Skill>("/skills", data),
  update: (id: string, data: SkillUpdate) => api.patch<Skill>(`/skills/${id}`, data),
  remove: (id: string) => api.delete<void>(`/skills/${id}`),
  readiness: (id: string) => api.get<SkillReadiness>(`/skills/${id}/readiness`),
  overview: (id: string) => api.get<StudentMasteryRow[]>(`/skills/${id}/overview`),
};
