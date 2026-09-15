import { api } from "@/lib/api-client";

export interface Skill {
  id: string;
  name: string;
  slug: string;
  description: string | null;
}

export interface SkillCreate {
  name: string;
  slug: string;
  description?: string;
}

export const skillsApi = {
  list: () => api.get<Skill[]>("/skills"),
  create: (data: SkillCreate) => api.post<Skill>("/skills", data),
};
