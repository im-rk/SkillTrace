import { api } from "@/lib/api-client";

export type QuizStatus = "in_progress" | "mastered" | "abandoned";

export interface QuizSession {
  id: string;
  skill_id: string;
  status: QuizStatus;
  initial_mastery: number;
  current_mastery: number;
  final_mastery: number | null;
  mastery_threshold: number;
  questions_answered: number;
  questions_correct: number;
  started_at: string;
  ended_at: string | null;
}

export interface PracticeQuestion {
  id: string;
  question_type: "multiple_choice" | "true_false" | "text_input";
  prompt: string;
  difficulty: "easy" | "medium" | "hard";
  // Sanitized by the backend -- never contains the correct answer.
  content: { choices?: { id: string; text: string }[] };
}

export interface NextQuestion {
  status: "in_progress" | "mastered" | "exhausted";
  mastery: number;
  question: PracticeQuestion | null;
}

export interface AnswerResult {
  is_correct: boolean;
  mastery_before: number;
  mastery_after: number;
  session_status: QuizStatus;
}

export interface SkillMastery {
  skill_id: string;
  name: string;
  slug: string;
  description: string | null;
  mastery_threshold: number;
  question_count: number;
  current_mastery: number | null;
  total_attempts: number;
  is_mastered: boolean;
}

export interface ProgressPoint {
  answered_at: string;
  mastery_before: number;
  mastery_after: number;
  is_correct: boolean;
  source: "practice" | "exam";
}

export interface Progress {
  skill_id: string;
  skill_name: string;
  initial_mastery: number;
  mastery_threshold: number;
  current_mastery: number | null;
  points: ProgressPoint[];
}

export const practiceApi = {
  mySkills: (studentId: string) => api.get<SkillMastery[]>(`/students/${studentId}/mastery`),
  start: (skillId: string) => api.post<QuizSession>("/quiz-sessions", { skill_id: skillId }),
  get: (sessionId: string) => api.get<QuizSession>(`/quiz-sessions/${sessionId}`),
  nextQuestion: (sessionId: string) => api.get<NextQuestion>(`/quiz-sessions/${sessionId}/next-question`),
  answer: (sessionId: string, questionId: string, submittedAnswer: string) =>
    api.post<AnswerResult>(`/quiz-sessions/${sessionId}/answer`, { question_id: questionId, submitted_answer: submittedAnswer }),
  quit: (sessionId: string) => api.post<QuizSession>(`/quiz-sessions/${sessionId}/quit`),
  progress: (studentId: string, skillId: string) =>
    api.get<Progress>(`/students/${studentId}/progress?skill_id=${encodeURIComponent(skillId)}`),
};

export const pct = (mastery: number) => Math.round(mastery * 100);
