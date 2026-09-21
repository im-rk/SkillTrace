"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { MyExams } from "@/features/enrollment/components/MyExams";

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <main>
      <h1>Dashboard</h1>
      <p>Signed in as {user?.role}</p>

      {user?.role === "student" ? (
        <>
          <section>
            <h2>My exams</h2>
            <MyExams />
            <p>
              <Link href="/enroll">Join an exam with an access code</Link>
            </p>
          </section>
        </>
      ) : (
        <nav>
          <ul>
            <li>
              <Link href="/admin/questions">Question bank</Link>
            </li>
            <li>
              <Link href="/admin/exams">Exams</Link>
            </li>
          </ul>
        </nav>
      )}

      <button onClick={handleLogout}>Log out</button>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
