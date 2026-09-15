import Link from "next/link";
import { LoginForm } from "@/features/auth/components/LoginForm";

export default function LoginPage() {
  return (
    <main>
      <h1>Log in</h1>
      <LoginForm />
      <p>
        Need an account? <Link href="/register">Register</Link>
      </p>
    </main>
  );
}
