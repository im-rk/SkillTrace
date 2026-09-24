"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/hooks/AuthContext";

interface NavItem {
  href: string;
  label: string;
}

const STUDENT_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/practice", label: "Practice" },
  { href: "/progress", label: "My progress" },
  { href: "/enroll", label: "Join exam" },
];

const STAFF_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/admin/exams", label: "Exams" },
  { href: "/admin/questions", label: "Question bank" },
  { href: "/admin/skills", label: "Skills" },
];

/** The app shell: brand, role-aware navigation, and who's signed in. Signed-out pages get just the brand. */
export function AppHeader() {
  const { user, status, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const nav = user?.role === "student" ? STUDENT_NAV : STAFF_NAV;

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link href={status === "authenticated" ? "/dashboard" : "/login"} className="brand">
          <span className="brand-mark" aria-hidden="true">
            ◈
          </span>
          SkillTrace
        </Link>

        {status === "authenticated" && user && (
          <>
            <nav aria-label="Main" className="app-nav">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href)) ? "page" : undefined}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="app-user">
              <span className="role-pill">{user.role}</span>
              <button type="button" data-variant="secondary" onClick={handleLogout}>
                Log out
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
