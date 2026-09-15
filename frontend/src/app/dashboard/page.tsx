"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";

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
      <p>Role: {user?.role}</p>
      {user?.role === "student" && <Link href="/enroll">Join an exam</Link>}
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
