import { api } from "@/lib/api-client";
import type { ExamSessionResponse } from "@/features/exam-taking/api/exam-taking.api";

export interface StudentExamResult {
  exam_id: string;
  questions_answered: number;
  total_score: number;
  final_mastery: number | null;
}

export interface ExamResultRow {
  user_id: string;
  display_name: string;
  total_score: number;
  final_mastery: number | null;
}

export interface ExamOverview {
  exam_id: string;
  results: ExamResultRow[];
}

export interface AuditEvent {
  timestamp: string;
  type: string;
  detail: Record<string, unknown>;
}

export interface AuditTrail {
  session_id: string;
  events: AuditEvent[];
}

export interface ItemAnalysisRow {
  question_id: string;
  prompt: string;
  sample_size: number;
  // null means not enough data yet (see backend/app/modules/results/item_analysis.py),
  // not zero -- render as "—", not "0%".
  p_value: number | null;
  discrimination: number | null;
}

export interface ItemAnalysis {
  exam_id: string;
  items: ItemAnalysisRow[];
}

export const resultsApi = {
  getMyResult: (examId: string) => api.get<StudentExamResult>(`/exams/${examId}/results`),
  getOverview: (examId: string) => api.get<ExamOverview>(`/exams/${examId}/overview`),
  getItemAnalysis: (examId: string) => api.get<ItemAnalysis>(`/exams/${examId}/item-analysis`),
  getAuditTrail: (sessionId: string) => api.get<AuditTrail>(`/exam-sessions/${sessionId}/audit-trail`),
  // Backend returns full ExamSessionResponse; only session_id is used here.
  getSessionIdForStudent: (examId: string, studentId: string) =>
    api.get<ExamSessionResponse>(`/exams/${examId}/students/${studentId}/session`),
};
