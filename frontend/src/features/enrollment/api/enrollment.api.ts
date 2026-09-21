import { api } from "@/lib/api-client";

export interface RedeemResult {
  enrolled: boolean;
  exam_id: string;
  access_method: "manual" | "access_code";
}

export interface MyExam {
  exam_id: string;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  phase: "upcoming" | "live" | "ended" | "closed";
  session_id: string | null;
  session_status: "in_progress" | "paused_disconnected" | "submitted" | "auto_submitted" | "expired" | null;
}

export const enrollmentApi = {
  myExams: () => api.get<MyExam[]>("/me/exams"),
  redeemAccessCode: (code: string) => api.post<RedeemResult>(`/access-codes/${encodeURIComponent(code)}/redeem`),
};
