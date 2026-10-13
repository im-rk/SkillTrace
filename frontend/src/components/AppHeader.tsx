"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/hooks/AuthContext";
import { BrandMark, Icon } from "@/components/ui/Icon";
import { initials } from "@/lib/format";

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
  { href: "/dashboard", label: "Overview" },
  { href: "/admin/skills", label: "Skills" },
  { href: "/admin/exams", label: "Exams" },
];

/** The app shell: brand, role-aware navigation, and who is signed in. Signed-out pages get just the brand. */
export function AppHeader() {
  const { user, status, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const nav = user?.role === "student" ? STUDENT_NAV : STAFF_NAV;
  const isActive = (href: string) => (href === "/dashboard" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`));

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link href={status === "authenticated" ? "/dashboard" : "/login"} className="brand">
          <BrandMark />
          SkillTrace
        </Link>

        {status === "authenticated" && user && (
          <>
            <nav aria-label="Main" className="nav">
              {nav.map((item) => (
                <Link key={item.href} href={item.href} aria-current={isActive(item.href) ? "page" : undefined}>
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="user-box">
              <div className="user-id">
                <span className="avatar" aria-hidden="true">
                  {initials(user.display_name)}
                </span>
                <div>
                  <div className="user-name">{user.display_name}</div>
                  <div className="user-role">{user.role}</div>
                </div>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>
                <Icon name="logout" small />
                Log out
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
