import { execSync } from "node:child_process";
import path from "node:path";
import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test";

export const DEMO_PASSWORD = "Passw0rd!demo";
export const INSTRUCTOR_EMAIL = "instructor@skilltrace.dev";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");

export function uniqueEmail(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.com`;
}

/** `datetime-local` wants local wall-clock time, "YYYY-MM-DDTHH:mm". */
export function localDateTime(offsetMinutes: number): string {
  const d = new Date(Date.now() + offsetMinutes * 60_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

export async function registerStudent(page: Page, email: string, name: string): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Display name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

export async function newSession(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  return { context, page: await context.newPage() };
}

/** Instructor creates an exam on the demo skill, assigns the given question prompts, returns ids + an access code. */
export async function createExamWithCode(
  page: Page,
  opts: { title: string; durationMinutes: number; prompts: string[] },
): Promise<{ examId: string; code: string }> {
  await page.goto("/admin/exams");
  await page.getByLabel("Title").fill(opts.title);
  await page.getByRole("combobox").selectOption({ label: "Fractions" }); // the seeded skill with a full question pool
  await page.getByLabel(/Start time/).fill(localDateTime(-5));
  await page.getByLabel(/End time/).fill(localDateTime(120));
  await page.getByLabel("Duration (minutes)").fill(String(opts.durationMinutes));
  await page.getByRole("button", { name: "Create exam" }).click();
  await expect(page).toHaveURL(/\/admin\/exams\/[0-9a-f-]{36}$/);
  const examId = page.url().split("/").pop()!;

  for (const prompt of opts.prompts) {
    await page.getByLabel(prompt, { exact: true }).check();
  }
  await page.getByRole("button", { name: "Assign selected questions" }).click();
  await expect(page.getByText("Questions assigned.")).toBeVisible();

  await page.getByRole("button", { name: "Generate access code" }).click();
  const codeLocator = page.locator("code").first();
  await expect(codeLocator).toBeVisible();
  return { examId, code: (await codeLocator.textContent())!.trim() };
}

export async function joinExam(page: Page, code: string): Promise<void> {
  await page.goto("/enroll");
  await page.getByLabel("Access code").fill(code);
  await page.getByRole("button", { name: "Join exam" }).click();
  await expect(page).toHaveURL(/\/exams\/[0-9a-f-]{36}$/);
}

export function backdateSession(sessionId: string, minutes: number): void {
  execSync(`uv run python -m scripts.e2e_helpers backdate-session ${sessionId} ${minutes}`, { cwd: BACKEND_DIR, stdio: "pipe" });
}
