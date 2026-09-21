import { expect, test, type Page } from "@playwright/test";
import { DEMO_PASSWORD, INSTRUCTOR_EMAIL, login, newSession, registerStudent, uniqueEmail } from "./helpers";

// Correct answers of the seeded "Fractions" skill (backend/scripts/seed_demo.py):
// MCQ -> the correct choice's text, true/false -> "True"/"False", text input -> the answer.
const CORRECT: Record<string, string> = {
  "What is 1/2 + 1/2?": "1",
  "Which fraction is the largest?": "1/2",
  "1/2 is equal to 2/4.": "True",
  "3/4 is greater than 1.": "False",
  "What is 1/4 written as a decimal?": "0.25",
  "What is the numerator of 5/8?": "5",
  "What is 2/3 + 1/6?": "5/6",
  "Simplify 12/16.": "3/4",
  "2/5 + 2/5 = 4/10.": "False",
  "What is 3/4 of 20?": "15",
  "What is 5/6 - 1/3?": "1/2",
  "1/3 and 2/6 are equivalent fractions.": "True",
  "What is (2/3) x (9/4)?": "3/2",
  "What is (3/5) / (9/10)?": "2/3",
  "What is 7/8 - 3/16, as a fraction over 16?": "11/16",
  "The reciprocal of 3/7 is 7/3.": "True",
  "Which is equal to 0.375?": "3/8",
  "What is 1 1/2 as an improper fraction?": "3/2",
};

const mastery = async (page: Page) => Number(await page.getByRole("meter", { name: "Mastery" }).getAttribute("aria-valuenow"));

/** Answers the question on screen (right or deliberately wrong) and returns what it saw. */
async function answerCurrent(page: Page, right: boolean): Promise<{ prompt: string; difficulty: string }> {
  const card = page.locator("fieldset");
  const prompt = (await card.locator("legend").textContent())!.trim();
  const difficulty = ((await card.getByText(/^Difficulty: /).textContent()) ?? "").replace("Difficulty: ", "");
  const correct = CORRECT[prompt];
  expect(correct, `unknown seeded question: ${prompt}`).toBeDefined();

  if ((await card.getByRole("textbox").count()) > 0) {
    await card.getByRole("textbox").fill(right ? correct : "zzz");
  } else if (correct === "True" || correct === "False") {
    await card.getByLabel(right ? correct : correct === "True" ? "False" : "True", { exact: true }).check();
  } else if (right) {
    await card.getByLabel(correct, { exact: true }).check();
  } else {
    const labels = await card.locator("label").allTextContents();
    await card.getByLabel(labels.find((l) => l.trim() !== correct)!.trim(), { exact: true }).check();
  }
  await card.getByRole("button", { name: "Submit answer" }).click();
  await expect(page.getByTestId("answer-feedback")).toBeVisible();
  return { prompt, difficulty };
}

test.describe("free-practice adaptive quiz (real browser, real backend)", () => {
  test("student practises until mastery; difficulty adapts; progress chart and instructor overview reflect it", async ({ browser }) => {
    const student = await newSession(browser);
    const page = student.page;
    const learner = `E2E Learner ${Date.now()}`;
    await registerStudent(page, uniqueEmail("learner"), learner);

    await page.getByRole("link", { name: "Adaptive practice" }).click();
    const fractions = page.getByTestId("practice-skill").filter({ hasText: "Fractions" });
    await expect(fractions).toContainText("Not started");
    await fractions.getByRole("button", { name: "Start practice" }).click();
    await expect(page).toHaveURL(/\/quiz\/[0-9a-f-]{36}$/);

    // Fresh student: P(L0) = 30% -> an easy question first.
    await expect(page.locator("fieldset")).toBeVisible();
    expect(await mastery(page)).toBe(30);

    const seenDifficulties: string[] = [];
    let last = await answerCurrent(page, false);
    seenDifficulties.push(last.difficulty);
    expect(last.difficulty).toBe("easy");
    await expect(page.getByRole("status")).toContainText("Not quite");
    expect(await mastery(page)).toBeLessThan(30); // a wrong answer lowers the estimate

    let answered = 1;
    let previous = await mastery(page);
    while (answered < 12) {
      await page.getByRole("button", { name: /Next question|See results/ }).click();
      if (await page.getByTestId("quiz-done").isVisible()) break;
      last = await answerCurrent(page, true);
      seenDifficulties.push(last.difficulty);
      answered += 1;
      const now = await mastery(page);
      expect(now).toBeGreaterThan(previous); // a right answer raises it
      previous = now;
      if (await page.getByRole("button", { name: "See results" }).isVisible()) break;
    }
    await page.getByRole("button", { name: "See results" }).click();

    await expect(page.getByTestId("quiz-done")).toContainText("You've mastered this skill");
    expect(await mastery(page)).toBeGreaterThanOrEqual(85);
    expect(seenDifficulties).toContain("medium"); // once past 40%, the tier moved up

    // The practice list now shows the skill as mastered, with no way to start it again.
    await page.goto("/practice");
    await expect(fractions).toContainText("Mastered");
    await expect(fractions.getByRole("button")).toHaveCount(0);

    // Progress chart: one point per answer, on a real rendered chart.
    await fractions.getByRole("link", { name: "Progress" }).click();
    await expect(page.getByTestId("progress-summary")).toContainText(`${answered} answers`);
    await expect(page.getByTestId("progress-chart").locator(".recharts-line-curve")).toBeVisible();
    await expect(page.getByTestId("progress-chart").locator(".recharts-line-dot")).toHaveCount(answered + 1); // + the starting estimate

    // Instructor sees the student in the skill's mastery table.
    const instructor = await newSession(browser);
    await login(instructor.page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);
    await instructor.page.goto("/admin/skills");
    await instructor.page.getByRole("combobox").selectOption({ label: "Fractions" });
    await expect(instructor.page.getByText(/Questions: \d+ easy, \d+ medium, \d+ hard/)).toBeVisible();
    await expect(instructor.page.getByRole("row", { name: new RegExp(learner) })).toContainText("Yes");

    await instructor.context.close();
    await student.context.close();
  });

  test("a student can end a session and resume where they left off", async ({ browser }) => {
    const student = await newSession(browser);
    const page = student.page;
    await registerStudent(page, uniqueEmail("quitter"), "E2E Quitter");
    await page.goto("/practice");
    const fractions = page.getByTestId("practice-skill").filter({ hasText: "Fractions" });
    await fractions.getByRole("button", { name: "Start practice" }).click();
    await expect(page.locator("fieldset")).toBeVisible();

    await answerCurrent(page, true);
    const afterOne = await mastery(page);
    await page.getByRole("button", { name: "Next question" }).click();
    await page.getByRole("button", { name: "End session" }).click();

    await expect(page).toHaveURL(/\/practice$/);
    await expect(fractions).toContainText(`Mastery ${afterOne}% after 1 answers`);
    await fractions.getByRole("button", { name: "Continue practice" }).click();
    await expect(page.locator("fieldset")).toBeVisible();
    expect(await mastery(page)).toBe(afterOne); // the mastery chain carries over into the new session

    await student.context.close();
  });

  test("instructor edits a skill's BKT parameters, sees the readiness warning, and deletes it", async ({ browser }) => {
    const instructor = await newSession(browser);
    const page = instructor.page;
    await login(page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);

    const name = `E2E skill ${Date.now()}`;
    await page.goto("/admin/questions");
    await page.getByLabel("New skill name").fill(name);
    await page.getByRole("button", { name: "Add skill" }).click();
    await expect(page.getByRole("option", { name }).first()).toBeAttached(); // created (don't navigate away mid-request)

    await page.goto("/admin/skills");
    await page.getByRole("combobox").selectOption({ label: name });
    await expect(page.getByRole("alert").filter({ hasText: "Not ready for adaptive practice" })).toContainText("easy or medium or hard");

    await page.getByLabel("Learning rate P(T)").fill("0.3");
    await page.getByLabel("Mastery threshold").fill("0.9");
    await page.getByRole("button", { name: "Save skill" }).click();
    await expect(page.getByText("Skill saved.")).toBeVisible();

    await page.reload();
    await page.getByRole("combobox").selectOption({ label: name });
    await expect(page.getByLabel("Learning rate P(T)")).toHaveValue("0.3");
    await expect(page.getByLabel("Mastery threshold")).toHaveValue("0.9");

    // Out-of-range values are blocked by the form (the API rejects them too: see the backend tests).
    await page.getByLabel("Guess P(G)").fill("1.5");
    expect(await page.getByLabel("Guess P(G)").evaluate((el) => (el as HTMLInputElement).validity.rangeOverflow)).toBe(true);

    page.once("dialog", (d) => d.accept());
    await page.getByRole("button", { name: "Delete skill" }).click();
    await expect(page.getByRole("option", { name })).toHaveCount(0);

    await instructor.context.close();
  });
});
