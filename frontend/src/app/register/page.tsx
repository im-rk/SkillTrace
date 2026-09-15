import Link from "next/link";
import { RegisterForm } from "@/features/auth/components/RegisterForm";

export default function RegisterPage() {
  return (
    <main>
      <h1>Create your account</h1>
      <RegisterForm />
      <p>
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </main>
  );
}
