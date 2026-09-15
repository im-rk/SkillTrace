"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { authApi } from "@/features/auth/api/auth.api";
import { useAuth } from "@/features/auth/hooks/AuthContext";

export function RegisterForm() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await authApi.register({ email, password, display_name: displayName });
      // Public registration always creates a student account; log the new
      // user straight in rather than making them re-type credentials.
      await login({ email, password });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Display name
        <input required value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
      </label>
      <label>
        Email
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label>
        Password
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={submitting}>
        {submitting ? "Creating account…" : "Create account"}
      </button>
    </form>
  );
}
