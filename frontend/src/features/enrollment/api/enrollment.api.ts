import { api } from "@/lib/api-client";

export interface RedeemResult {
  enrolled: boolean;
  exam_id: string;
  access_method: "manual" | "access_code";
}

export const enrollmentApi = {
  redeemAccessCode: (code: string) => api.post<RedeemResult>(`/access-codes/${encodeURIComponent(code)}/redeem`),
};
