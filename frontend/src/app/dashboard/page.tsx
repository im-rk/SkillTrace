"use client";

import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { StudentDashboard } from "@/features/dashboard/StudentDashboard";
import { StaffDashboard } from "@/features/dashboard/StaffDashboard";

function DashboardContent() {
  const { user } = useAuth();
  if (!user) return null;
  return user.role === "student" ? <StudentDashboard /> : <StaffDashboard />;
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
