import { api } from "@/lib/api-client";

export interface StudentExamQuestion {
  question_id: string;
  prompt: string;
  question_type: "multiple_choice" | "true_false" | "text_input";
  difficulty: "easy" | "medium" | "hard";
  display_order: number;
  points: number;
  // Sanitized by the backend -- never contains the correct answer.
  content: { choices?: { id: string; text: string }[] };
}

export interface StudentExamView {
  exam_id: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  questions: StudentExamQuestion[];
}

export interface ExamSessionResponse {
  session_id: string;
  exam_id: string;
  status: "in_progress" | "paused_disconnected" | "submitted" | "auto_submitted" | "expired";
  started_at: string;
}

export interface SessionTiming {
  elapsed_active_seconds: number;
  total_duration_seconds: number;
  status: string;
}

export interface SubmissionAccepted {
  status: "accepted";
  log_id: string;
}

export interface SubmissionStatus {
  log_id: string;
  status: "pending" | "processing" | "completed" | "failed";
}

export interface SessionSubmitted {
  session_id: string;
  status: ExamSessionResponse["status"];
  completed_at: string | null;
}

export const ENDED_SESSION_STATUSES: ExamSessionResponse["status"][] = ["submitted", "auto_submitted", "expired"];

export const examTakingApi = {
  getExamForStudent: (examId: string) => api.get<StudentExamView>(`/exams/${examId}/questions`),
  startExam: (examId: string) => api.post<ExamSessionResponse>(`/exams/${examId}/start`),
  submitExam: (sessionId: string) => api.post<SessionSubmitted>(`/exam-sessions/${sessionId}/submit`),
  getSessionTiming: (sessionId: string) => api.get<SessionTiming>(`/exam-sessions/${sessionId}/timing`),
  submitAnswer: (sessionId: string, questionId: string, answer: string) =>
    api.post<SubmissionAccepted>(`/exam-sessions/${sessionId}/submit-answer`, {
      question_id: questionId,
      answer,
    }),
  getSubmissionStatus: (logId: string) => api.get<SubmissionStatus>(`/submissions/${logId}`),
};
