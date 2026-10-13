import { expect, test } from "@playwright/test";
import { DEMO_PASSWORD, INSTRUCTOR_EMAIL, joinExam, localDateTime, login, newSession, registerStudent, uniqueEmail } from "./helpers";

/** The whole instructor story, in the UI: skill, then its question bank, then an exam and an access code; then a student takes it. */
test("instructor builds a skill, its question bank and an exam from nothing; a student then takes it", async ({ browser }) => {
  const instructor = await newSession(browser);
  const page = instructor.page;
  await login(page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);

  // 1. A new skill.
  const skillName = `Teacher skill ${Date.now()}`;
  await page.goto("/admin/skills");
  await page.getByRole("button", { name: "New skill" }).click();
  await page.getByLabel("Skill name").fill(skillName);
  await page.getByLabel("Description (optional)").fill("Built end to end by the browser test");
  await page.getByRole("button", { name: "Create skill" }).click();
  await expect(page.getByRole("heading", { name: skillName })).toBeVisible();
  await expect(page.getByText("Not ready yet")).toBeVisible();

  // 2. Its question bank: one of each type, one per difficulty.
  const addQuestion = async (prompt: string, level: "Easy" | "Medium" | "Hard", fill: () => Promise<void>) => {
    await page.getByRole("button", { name: "Add question" }).click();
    await page.getByRole("radio", { name: level, exact: true }).click();
    await page.getByLabel("Question", { exact: true }).fill(prompt);
    await fill();
    await page.getByRole("button", { name: "Save question" }).click();
    await expect(page.getByTestId("question-row").filter({ hasText: prompt })).toBeVisible();
  };

  await addQuestion("Which is a primary colour?", "Easy", async () => {
    // Save stays disabled until every option is filled and one is marked correct.
    await expect(page.getByRole("button", { name: "Save question" })).toBeDisabled();
    await page.getByRole("textbox", { name: "Option A" }).fill("Green");
    await page.getByRole("textbox", { name: "Option B" }).fill("Blue");
    await page.getByRole("textbox", { name: "Option C" }).fill("Orange");
    await page.getByRole("textbox", { name: "Option D" }).fill("Purple");
    await expect(page.getByRole("button", { name: "Save question" })).toBeDisabled();
    await page.getByRole("button", { name: "Mark option B as correct" }).click();
  });
  await expect(page.getByText(/no medium or hard/)).toBeVisible();

  await addQuestion("The sky is blue on a clear day.", "Medium", async () => {
    await page.getByRole("radio", { name: "True / false" }).click();
    await page.getByRole("radio", { name: "True", exact: true }).click();
  });
  await addQuestion("Name the capital of France.", "Hard", async () => {
    await page.getByRole("radio", { name: "Short answer" }).click();
    await page.getByLabel("Correct answer").fill("Paris");
  });

  await expect(page.getByText("Ready for practice and exams")).toBeVisible();
  await expect(page.getByTestId("question-row")).toHaveCount(3);

  // 3. An exam from that skill: the form opens with the skill already chosen.
  await page.getByRole("link", { name: "Create an exam from this skill" }).click();
  await expect(page.locator("#exam-skill")).toContainText(skillName);
  await page.getByLabel("Title").fill(`Teacher exam ${Date.now()}`);
  await page.getByLabel(/Start time/).fill(localDateTime(-5));
  await page.getByLabel(/End time/).fill(localDateTime(120));
  await page.getByRole("button", { name: "Create exam" }).click();
  await expect(page).toHaveURL(/\/admin\/exams\/[0-9a-f-]{36}$/);

  // 4. Choose all three questions, save, and generate the code.
  for (const prompt of ["Which is a primary colour?", "The sky is blue on a clear day.", "Name the capital of France."]) {
    await page.getByLabel(prompt, { exact: true }).check();
  }
  await expect(page.getByText(/3 questions selected/)).toBeVisible();
  await page.getByRole("button", { name: "Save questions" }).click();
  await expect(page.getByText("Questions saved.")).toBeVisible();
  await page.getByRole("button", { name: "Generate access code" }).click();
  const code = (await page.locator('code[aria-label="Access code"]').textContent())!.trim();
  expect(code).toMatch(/\w{4,}/);

  // 5. A student joins with the code and answers.
  const student = await newSession(browser);
  await registerStudent(student.page, uniqueEmail("teacherflow"), "Flow Student");
  await joinExam(student.page, code);
  const exam = student.page;
  await expect(exam.getByRole("timer")).toContainText(/\d+:\d\d/);
  const first = exam.getByRole("group", { name: "Which is a primary colour?" });
  await first.getByLabel("Blue", { exact: true }).check();
  await first.getByRole("button", { name: "Submit answer" }).click();
  await expect(first.getByText("Answer recorded")).toBeVisible();
  await expect(exam.getByText("1 of 3 answered")).toBeVisible();

  // 6. The instructor sees the student on the roster.
  await page.reload();
  await expect(page.getByText("Flow Student")).toBeVisible();

  await instructor.context.close();
  await student.context.close();
});
