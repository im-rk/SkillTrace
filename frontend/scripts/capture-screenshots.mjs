// Captures the documentation / presentation screenshots from the running stack (frontend :3000, API :8000).
//   node scripts/capture-screenshots.mjs <live-exam-access-code>
// Run `uv run python -m scripts.demo_simulate` (backend) first so the screens have data.
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const OUT = path.resolve(import.meta.dirname, "../../presentation/screenshots");
const API = "http://localhost:8000";
const WEB = "http://localhost:3000";
const PASSWORD = "Passw0rd!demo";
const CODE = process.argv[2];
if (!CODE) throw new Error("usage: node scripts/capture-screenshots.mjs <live-exam-access-code>");
fs.mkdirSync(OUT, { recursive: true });

// Decimals answer key (matches backend/scripts/demo_simulate.py)
const CORRECT = {
  "What is 0.5 + 0.25?": "0.75", "0.5 is equal to 1/2.": "True", "What is 0.1 + 0.2?": "0.3", "Which is the largest?": "0.9",
  "What is 1.5 x 2?": "3", "0.30 is greater than 0.3.": "False", "What is 7.5 divided by 5?": "1.5",
  "Round 3.14159 to two decimal places.": "3.14", "What is 0.04 x 0.5?": "0.02", "0.1 x 0.1 = 0.1": "False",
  "What is 2.5 squared?": "6.25", "What is 12.6 / 0.3?": "42",
};

const browser = await chromium.launch();
const open = async (w = 1440, h = 900) => {
  const context = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: "light" });
  return { context, page: await context.newPage() };
};
const shot = async (page, name, fullPage = false) => {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage });
  console.log("saved", name);
};
const login = async (page, email) => {
  await page.goto(`${WEB}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(/dashboard/);
};
const ensureUser = async (page, email, name) => {
  await fetch(`${API}/auth/register`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password: PASSWORD, display_name: name }) });
  await login(page, email);
};

async function answer(page, right) {
  const card = page.locator("fieldset");
  const prompt = (await card.locator("legend").textContent()).trim();
  const correct = CORRECT[prompt];
  if (correct === undefined) throw new Error("unknown question " + prompt);
  if ((await card.getByRole("textbox").count()) > 0) await card.getByRole("textbox").fill(right ? correct : "zzz");
  else if (correct === "True" || correct === "False") await card.getByLabel(right ? correct : correct === "True" ? "False" : "True", { exact: true }).check();
  else if (right) await card.getByLabel(correct, { exact: true }).check();
  else {
    const labels = await card.locator("label").allTextContents();
    await card.getByLabel(labels.find((l) => l.trim() !== correct).trim(), { exact: true }).check();
  }
  await card.getByRole("button", { name: "Submit answer" }).click();
  await page.getByTestId("answer-feedback").waitFor();
}
const next = async (page) => {
  await page.getByRole("button", { name: /Next question|See results/ }).click();
  await page.getByTestId("answer-feedback").waitFor({ state: "detached" });
};
const startDecimals = async (page) => {
  await page.goto(`${WEB}/practice`);
  await page.getByTestId("practice-skill").filter({ hasText: "Decimals" }).getByRole("button", { name: /Start practice|Continue practice/ }).click();
  await page.locator("fieldset").waitFor();
};

const tok = async (email) => (await (await fetch(`${API}/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password: PASSWORD }) })).json()).access_token;
const it = await tok("instructor@skilltrace.dev");
const get = async (p) => (await fetch(`${API}${p}`, { headers: { authorization: `Bearer ${it}` } })).json();
const skills = await get("/skills");
const exams = await get("/exams");
const fractions = skills.find((s) => s.slug === "fractions");
const midterm = exams.find((e) => e.title === "Fractions Midterm Quiz");

// ---- signed out ------------------------------------------------------------------
{ const { context, page } = await open(); await page.goto(`${WEB}/login`); await shot(page, "shot_01_login"); await context.close(); }

// ---- instructor ------------------------------------------------------------------
{
  const { context, page } = await open();
  await login(page, "instructor@skilltrace.dev");
  await shot(page, "shot_19_instructor_dashboard", true);
  await page.goto(`${WEB}/admin/skills`);
  await page.getByTestId("skill-card").first().waitFor();
  await shot(page, "shot_22_skills_list");
  await page.goto(`${WEB}/admin/skills/${fractions.id}`);
  await page.getByTestId("question-row").first().waitFor();
  await shot(page, "shot_13_skill_questions");
  await page.getByRole("button", { name: "Add question" }).click();
  await page.getByRole("textbox", { name: "Option A" }).fill("3/4");
  await page.getByRole("textbox", { name: "Option B" }).fill("5/8");
  await page.getByRole("textbox", { name: "Option C" }).fill("1/2");
  await page.getByRole("textbox", { name: "Option D" }).fill("7/8");
  await page.getByLabel("Question", { exact: true }).fill("What is 1/4 + 1/2?");
  await page.getByRole("button", { name: "Mark option A as correct" }).click();
  await shot(page, "shot_23_question_editor");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Draft with AI" }).click();
  await page.getByLabel("Focus (optional)").fill("adding fractions with unlike denominators");
  await page.getByRole("button", { name: "Draft questions" }).click();
  await page.getByTestId("ai-drafts").waitFor({ timeout: 60000 });
  await shot(page, "shot_24_ai_drafts", true);
  await page.getByRole("tab", { name: "Learning model" }).click();
  await shot(page, "shot_09_skill_learning_model");
  await page.getByRole("tab", { name: /Students/ }).click();
  await shot(page, "shot_25_skill_students", true);
  await page.goto(`${WEB}/admin/exams`);
  await page.getByText("Fractions Live Quiz").waitFor();
  await shot(page, "shot_12_admin_exams");
  await page.goto(`${WEB}/admin/exams/new?skill=${fractions.id}`);
  await page.getByLabel("Title").fill("Fractions final check");
  await page.getByRole("button", { name: "Open now for 3 hours" }).click();
  await shot(page, "shot_26_exam_new", true);
  await page.goto(`${WEB}/admin/exams/${midterm.id}`);
  await page.getByText("Enrolled students").waitFor();
  await shot(page, "shot_20_admin_exam_detail", true);
  await page.goto(`${WEB}/admin/exams/${midterm.id}/results`);
  await page.getByRole("row", { name: /Aarav/ }).waitFor({ timeout: 60000 });
  await shot(page, "shot_10_exam_results");
  await shot(page, "shot_11_item_analysis", true);
  await page.getByRole("button", { name: "Audit trail" }).first().click();
  await page.getByRole("link", { name: "View audit trail" }).first().click();
  await page.getByText("Answer submitted").first().waitFor();
  await shot(page, "shot_21_audit_trail", true);
  await context.close();
}

// ---- student: the demo student's own screens -------------------------------------------
{
  const { context, page } = await open();
  await login(page, "student@skilltrace.dev");
  await shot(page, "shot_02_student_dashboard");
  await page.goto(`${WEB}/practice`);
  await page.getByTestId("practice-skill").first().waitFor();
  await shot(page, "shot_15_practice_skill_list");
  await page.goto(`${WEB}/exams/${midterm.id}/results`);
  await page.getByText("Total score").waitFor();
  await shot(page, "shot_14_student_exam_result");
  await page.goto(`${WEB}/progress`);
  await page.getByTestId("progress-chart").waitFor();
  await shot(page, "shot_16_progress_overview", true);
  await context.close();
}

// ---- student: wrong first, then a recovery (chart with the Viterbi marker) ----------------
{
  const { context, page } = await open();
  await ensureUser(page, "priya@skilltrace.dev", "Priya Raman");
  await startDecimals(page);
  await shot(page, "shot_03_practice_question");
  await answer(page, false);
  await shot(page, "shot_05_gauge_after_wrong");
  for (const right of [true, false, true, true]) {
    await next(page);
    if (await page.getByTestId("quiz-done").isVisible()) break;
    await answer(page, right);
  }
  await page.goto(`${WEB}/progress`);
  await page.getByTestId("progress-chart").waitFor();
  await shot(page, "shot_07_progress_chart", true);
  await context.close();
}

// ---- student: right, right -> mastered ----------------------------------------------------
{
  const { context, page } = await open();
  await ensureUser(page, "tara@skilltrace.dev", "Tara Joseph");
  await startDecimals(page);
  await answer(page, true);
  await shot(page, "shot_04_gauge_after_correct");
  await next(page);
  await answer(page, true);
  await page.getByRole("button", { name: "See results" }).click();
  await page.getByTestId("quiz-done").waitFor();
  await shot(page, "shot_06_mastered");
  await context.close();
}

// ---- student: joins and takes the live exam ---------------------------------------------------
{
  const { context, page } = await open();
  await ensureUser(page, "neha@skilltrace.dev", "Neha Kapoor");
  await page.goto(`${WEB}/enroll`);
  await page.getByLabel("Access code").fill(CODE);
  await shot(page, "shot_17_redeem_code");
  await page.getByRole("button", { name: "Join exam" }).click();
  await page.getByRole("timer").waitFor();
  const g = page.getByRole("group", { name: "What is 1/2 + 1/2?" });
  await g.getByLabel("1", { exact: true }).check();
  await g.getByRole("button", { name: "Submit answer" }).click();
  await g.getByText("Answer recorded").waitFor();
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, "shot_08_exam_taking");
  await page.getByRole("button", { name: "Finish exam" }).click();
  await page.getByRole("button", { name: "Yes, submit" }).click();
  await page.getByTestId("exam-ended").waitFor();
  await shot(page, "shot_18_exam_submitted");
  await context.close();
}

await browser.close();
