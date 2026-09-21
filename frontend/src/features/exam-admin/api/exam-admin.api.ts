import { api } from "@/lib/api-client";

export type ExamStatus = "draft" | "scheduled" | "live" | "closed";

export interface Exam {
  id: string;
  title: string;
  description: string | null;
  skill_id: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  status: ExamStatus;
  // Derived from the clock (upcoming/live/ended) and Exam.status (closed) -- what people mean by "status".
  phase: "upcoming" | "live" | "ended" | "closed";
}

export interface ExamCreate {
  title: string;
  description?: string;
  skill_id: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
}

export interface AssignedQuestion {
  question_id: string;
  display_order: number;
  points: string;
}

export interface EnrolledStudent {
  student_id: string;
  display_name: string;
  email: string;
  enrolled_at: string;
}

export interface AccessCode {
  code: string;
  exam_id: string;
  max_uses: number | null;
  times_used: number;
  expires_at: string | null;
}

export interface AccessCodeCreate {
  max_uses?: number;
  expires_at?: string;
}

export const examAdminApi = {
  list: () => api.get<Exam[]>("/exams"),
  get: (examId: string) => api.get<Exam>(`/exams/${examId}`),
  create: (data: ExamCreate) => api.post<Exam>("/exams", data),
  assignQuestions: (examId: string, questions: AssignedQuestion[]) =>
    api.post<void>(`/exams/${examId}/questions`, { questions }),
  close: (examId: string) => api.post<Exam>(`/exams/${examId}/close`),
  listEnrollments: (examId: string) => api.get<EnrolledStudent[]>(`/exams/${examId}/enrollments`),
  listAccessCodes: (examId: string) => api.get<AccessCode[]>(`/exams/${examId}/access-codes`),
  createAccessCode: (examId: string, data: AccessCodeCreate) =>
    api.post<AccessCode>(`/exams/${examId}/access-codes`, data),
};
