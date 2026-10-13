import { api } from "@/lib/api-client";

export type UserRole = "student" | "instructor" | "admin";

export interface CurrentUser {
  user_id: string;
  role: UserRole;
  display_name: string;
  email: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  display_name: string;
}

export interface RegisteredUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export const authApi = {
  register: (data: RegisterPayload) => api.post<RegisteredUser>("/auth/register", data),
  login: (data: LoginPayload) => api.post<LoginResult>("/auth/login", data),
  logout: () => api.post<void>("/auth/logout"),
  me: () => api.get<CurrentUser>("/auth/me"),
};
