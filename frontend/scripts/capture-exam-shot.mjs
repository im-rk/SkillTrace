// Re-takes the exam-taking screenshot as a viewport shot (sticky header/timer render badly in full-page mode).
//   node scripts/capture-exam-shot.mjs <live-exam-access-code>
import path from "node:path";
import { chromium } from "@playwright/test";

const OUT = path.resolve(import.meta.dirname, "../../presentation/screenshots/shot_08_exam_taking.png");
const API = "http://localhost:8000", PASSWORD = "Passw0rd!demo", CODE = process.argv[2];
const email = "neha@skilltrace.dev";
await fetch(`${API}/auth/register`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password: PASSWORD, display_name: "Neha Kapoor" }) });
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await page.goto("http://localhost:3000/login");
await page.getByLabel("Email").fill(email);
await page.getByLabel("Password").fill(PASSWORD);
await page.getByRole("button", { name: "Log in" }).click();
await page.waitForURL(/dashboard/);
await page.goto("http://localhost:3000/enroll");
await page.getByLabel("Access code").fill(CODE);
await page.getByRole("button", { name: "Join exam" }).click();
await page.getByRole("timer").waitFor();
const g = page.getByRole("group", { name: "What is 1/2 + 1/2?" });
await g.getByLabel("1", { exact: true }).check();
await g.getByRole("button", { name: "Submit answer" }).click();
await g.getByText("Answer recorded").waitFor();
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(800);
await page.screenshot({ path: OUT });
await browser.close();
console.log("saved shot_08_exam_taking");
