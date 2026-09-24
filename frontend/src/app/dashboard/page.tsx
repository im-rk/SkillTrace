"use client";

import Link from "next/link";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { MyExams } from "@/features/enrollment/components/MyExams";

function DashboardContent() {
  const { user } = useAuth();

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
          <section>
            <h2>Practice</h2>
            <ul>
              <li>
                <Link href="/practice">Adaptive practice</Link>
              </li>
              <li>
                <Link href="/progress">My progress</Link>
              </li>
            </ul>
          </section>
        </>
      ) : (
        <nav>
          <ul>
            <li>
              <Link href="/admin/questions">Question bank</Link>
            </li>
            <li>
              <Link href="/admin/skills">Skills</Link>
            </li>
            <li>
              <Link href="/admin/exams">Exams</Link>
            </li>
          </ul>
        </nav>
      )}
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
