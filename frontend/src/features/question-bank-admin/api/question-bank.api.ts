import { api } from "@/lib/api-client";

export type QuestionType = "multiple_choice" | "true_false" | "text_input";
export type Difficulty = "easy" | "medium" | "hard";

export interface MCQContent {
  choices: { id: string; text: string }[];
  correct_choice_id: string;
}
export interface TrueFalseContent {
  correct_answer: boolean;
}
export interface TextInputContent {
  correct_answer: string;
  case_sensitive: boolean;
}
export type QuestionContent = MCQContent | TrueFalseContent | TextInputContent;

export interface QuestionCreate {
  skill_id: string;
  question_type: QuestionType;
  prompt: string;
  difficulty: Difficulty;
  content: QuestionContent;
  tags: string[];
}

export interface Question {
  id: string;
  skill_id: string;
  question_type: QuestionType;
  prompt: string;
  difficulty: Difficulty;
  content: QuestionContent;
  version: number;
  tags: string[];
}

export interface BulkImportRowResult {
  row_number: number;
  status: "success" | "failed";
  question_id: string | null;
  error: string | null;
}

export interface BulkImportResponse {
  total_rows: number;
  succeeded: number;
  failed: number;
  results: BulkImportRowResult[];
}

export interface GenerateQuestionsResponse {
  drafts: QuestionCreate[];
  discarded: number;
}

export const questionBankApi = {
  // The backend requires skill_id or tags -- there's no "list every
  // question" mode -- so this always scopes to one skill.
  list: (skillId: string) => api.get<Question[]>(`/question-bank/questions?skill_id=${skillId}`),
  // LLM drafts only -- nothing is saved until the instructor approves them via create().
  generate: (body: { skill_id: string; count: number; difficulty: Difficulty | "mixed"; topic?: string }) =>
    api.post<GenerateQuestionsResponse>("/question-bank/generate", body),
  create: (data: QuestionCreate) => api.post<Question>("/question-bank/questions", data),
  delete: (questionId: string) => api.delete<void>(`/question-bank/questions/${questionId}`),
  bulkImportCsv: (skillId: string, file: File) => {
    const form = new FormData();
    form.append("skill_id", skillId);
    form.append("file", file);
    return api.postForm<BulkImportResponse>("/question-bank/bulk-import/csv", form);
  },
  bulkImportJson: (skillId: string, rows: Record<string, unknown>[]) =>
    api.post<BulkImportResponse>("/question-bank/bulk-import", { skill_id: skillId, rows }),
};
