// Captures the presentation screenshots from the running stack (frontend :3000, API :8000).
//   node scripts/capture-screenshots.mjs <live-exam-access-code>
// Run `uv run python -m scripts.demo_simulate` (backend) first so the screens have data.
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const OUT = path.resolve(import.meta.dirname, "../../presentation/screenshots");
const API = "http://localhost:8000";
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
const EXAM_CORRECT = { "What is 1/2 + 1/2?": "1", "1/2 is equal to 2/4.": "True", "What is 1/4 written as a decimal?": "0.25" };

const browser = await chromium.launch();
const ctx = async () => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: "light" });
  return { context, page: await context.newPage() };
};
const shot = async (page, name, opts = {}) => {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), ...opts });
  console.log("saved", name);
};
const login = async (page, email) => {
  await page.goto("http://localhost:3000/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(/dashboard/);
};
const register = async (page, email, name) => {
  await page.goto("http://localhost:3000/register");
  await page.getByLabel("Display name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/dashboard/);
};
const ensureUser = async (page, email, name) => {
  const res = await fetch(`${API}/auth/register`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password: PASSWORD, display_name: name }) });
  await login(page, email);
  return res.status;
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
const startDecimals = async (page) => {
  await page.goto("http://localhost:3000/practice");
  await page.getByTestId("practice-skill").filter({ hasText: "Decimals" }).getByRole("button", { name: /Start practice|Continue practice/ }).click();
  await page.locator("fieldset").waitFor();
};

// ---- ids via API ------------------------------------------------------------------------
const tok = async (email) => (await (await fetch(`${API}/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password: PASSWORD }) })).json()).access_token;
const it = await tok("instructor@skilltrace.dev");
const exams = await (await fetch(`${API}/exams`, { headers: { authorization: `Bearer ${it}` } })).json();
const midterm = exams.find((e) => e.title === "Fractions Midterm Quiz").id;

// 1. login page
{ const { context, page } = await ctx(); await page.goto("http://localhost:3000/login"); await shot(page, "shot_01_login"); await context.close(); }

// 2. student dashboard (has the midterm result)
{
  const { context, page } = await ctx();
  await login(page, "student@skilltrace.dev");
  await shot(page, "shot_02_student_dashboard", { fullPage: true });
  await page.goto(`http://localhost:3000/exams/${midterm}/results`);
  await shot(page, "shot_14_student_exam_result");
  await page.goto("http://localhost:3000/practice");
  await shot(page, "shot_15_practice_skill_list");
  await page.goto("http://localhost:3000/progress");
  await shot(page, "shot_16_progress_overview", { fullPage: true });
  await context.close();
}

// 3,5,7. Priya: wrong, then right/wrong/right/right -> chart with the Viterbi marker
{
  const { context, page } = await ctx();
  await ensureUser(page, "priya@skilltrace.dev", "Priya Raman");
  await startDecimals(page);
  await shot(page, "shot_03_practice_question");
  await answer(page, false);
  await shot(page, "shot_05_gauge_after_wrong");
  for (const right of [true, false, true, true]) {
    const next = page.getByRole("button", { name: /Next question|See results/ });
    await next.click();
    if (await page.getByTestId("quiz-done").isVisible()) break;
    await answer(page, right);
  }
  const results = page.getByRole("button", { name: "See results" });
  if (await results.isVisible()) await results.click();
  await page.goto("http://localhost:3000/practice");
  await page.getByTestId("practice-skill").filter({ hasText: "Decimals" }).getByRole("link", { name: "Progress" }).click();
  await page.getByTestId("progress-chart").waitFor();
  await shot(page, "shot_07_progress_chart", { fullPage: true });
  await context.close();
}

// 4,6. Tara: right, right -> mastered
{
  const { context, page } = await ctx();
  await ensureUser(page, "tara@skilltrace.dev", "Tara Joseph");
  await startDecimals(page);
  await answer(page, true);
  await shot(page, "shot_04_gauge_after_correct");
  await page.getByRole("button", { name: /Next question/ }).click();
  await page.locator("fieldset").waitFor();
  await answer(page, true);
  await shot(page, "shot_06a_before_results");
  const results = page.getByRole("button", { name: "See results" });
  if (await results.isVisible()) await results.click();
  await page.getByTestId("quiz-done").waitFor();
  await shot(page, "shot_06_mastered");
  await context.close();
}

// 8. Ishaan takes the live exam
{
  const { context, page } = await ctx();
  await ensureUser(page, "ishaan@skilltrace.dev", "Ishaan Patel");
  await page.goto("http://localhost:3000/enroll");
  await page.getByLabel("Access code").fill(CODE);
  await shot(page, "shot_17_redeem_code");
  await page.getByRole("button", { name: "Join exam" }).click();
  await page.getByRole("timer").waitFor();
  for (const [prompt, ans] of Object.entries(EXAM_CORRECT)) {
    const g = page.getByRole("group", { name: prompt });
    if ((await g.count()) === 0) continue;
    if ((await g.getByRole("textbox").count()) > 0) await g.getByRole("textbox").fill(ans);
    else await g.getByLabel(ans, { exact: true }).check();
    await g.getByRole("button", { name: "Submit answer" }).click();
    await g.getByText("Answer recorded").waitFor();
  }
  await shot(page, "shot_08_exam_taking", { fullPage: true });
  await page.getByRole("button", { name: "Finish exam" }).click();
  await page.getByRole("button", { name: "Yes, submit" }).click();
  await page.getByTestId("exam-ended").waitFor();
  await shot(page, "shot_18_exam_submitted");
  await context.close();
}

// instructor screens
{
  const { context, page } = await ctx();
  await login(page, "instructor@skilltrace.dev");
  await shot(page, "shot_19_instructor_dashboard");
  await page.goto("http://localhost:3000/admin/skills");
  await page.getByRole("combobox").selectOption({ label: "Fractions" });
  await page.getByText(/Questions: \d+ easy/).waitFor();
  await shot(page, "shot_09_admin_skills", { fullPage: true });
  await page.goto("http://localhost:3000/admin/questions");
  await shot(page, "shot_13_admin_questions", { fullPage: true });
  await page.goto("http://localhost:3000/admin/exams");
  await shot(page, "shot_12_admin_exams", { fullPage: true });
  await page.goto(`http://localhost:3000/admin/exams/${midterm}`);
  await shot(page, "shot_20_admin_exam_detail", { fullPage: true });
  await page.goto(`http://localhost:3000/admin/exams/${midterm}/results`);
  await page.getByRole("row", { name: /Aarav/ }).waitFor({ timeout: 60000 });
  await shot(page, "shot_10_exam_results");
  await shot(page, "shot_11_item_analysis", { fullPage: true });
  await page.getByRole("button", { name: "Audit trail" }).click().catch(() => {});
  await page.getByRole("link", { name: "View audit trail" }).first().click().catch(() => {});
  await page.waitForTimeout(1500);
  await shot(page, "shot_21_audit_trail", { fullPage: true });
  await context.close();
}

await browser.close();
