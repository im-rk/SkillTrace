import { expect, test } from "@playwright/test";
import {
  DEMO_PASSWORD,
  INSTRUCTOR_EMAIL,
  backdateSession,
  createExamWithCode,
  joinExam,
  login,
  newSession,
  registerStudent,
  uniqueEmail,
} from "./helpers";

const PROMPTS = ["What is 1/2 + 1/2?", "1/2 is equal to 2/4.", "What is 1/4 written as a decimal?"];

test.describe("exam journey (instructor + student, real browser, real backend)", () => {
  test("instructor builds an exam, student takes it, results appear after the exam closes", async ({ browser }) => {
    const instructor = await newSession(browser);
    await login(instructor.page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);
    const { examId, code } = await createExamWithCode(instructor.page, {
      title: `E2E exam ${Date.now()}`,
      durationMinutes: 30,
      prompts: PROMPTS,
    });

    // --- student: register, redeem the code, take the exam -----------------
    const student = await newSession(browser);
    const studentEmail = uniqueEmail("student");
    await registerStudent(student.page, studentEmail, "E2E Student");
    await joinExam(student.page, code);

    const page = student.page;
    await expect(page.getByRole("heading", { name: /E2E exam/ })).toBeVisible();
    await expect(page.getByRole("timer")).toContainText(/\d+:\d\d/); // server-synced countdown, not "Loading"
    await expect(page.getByText(/Connection lost|Connecting/)).toHaveCount(0); // WebSocket really connected

    // MCQ (correct: "1"), true/false (correct: True), text input (correct: 0.25)
    await page.getByRole("group", { name: PROMPTS[0] }).getByLabel("1", { exact: true }).check();
    await page.getByRole("group", { name: PROMPTS[0] }).getByRole("button", { name: "Submit answer" }).click();
    await expect(page.getByRole("group", { name: PROMPTS[0] }).getByText("Answer recorded")).toBeVisible(); // async grading finished

    await page.getByRole("group", { name: PROMPTS[1] }).getByLabel("True").check();
    await page.getByRole("group", { name: PROMPTS[1] }).getByRole("button", { name: "Submit answer" }).click();
    await expect(page.getByRole("group", { name: PROMPTS[1] }).getByText("Answer recorded")).toBeVisible();

    await page.getByRole("group", { name: PROMPTS[2] }).getByRole("textbox").fill("0.25");
    await page.getByRole("group", { name: PROMPTS[2] }).getByRole("button", { name: "Submit answer" }).click();
    await expect(page.getByRole("group", { name: PROMPTS[2] }).getByText("Answer recorded")).toBeVisible();

    // An answered question is final.
    await expect(page.getByRole("group", { name: PROMPTS[0] }).getByRole("button", { name: "Submit answer" })).toBeDisabled();

    await page.getByRole("button", { name: "Finish exam" }).click();
    await page.getByRole("button", { name: "Yes, submit" }).click();
    await expect(page.getByTestId("exam-ended")).toContainText("submitted");

    // Reloading an already-finished exam does not let the student back in.
    await page.reload();
    await expect(page.getByTestId("exam-ended")).toContainText("already finished");

    // Results are not available until the exam closes.
    await page.goto(`/exams/${examId}/results`);
    await expect(page.getByText("Results aren't available yet")).toBeVisible();

    // --- instructor closes the exam; results are computed once, async -------
    await instructor.page.goto(`/admin/exams/${examId}`);
    instructor.page.once("dialog", (d) => d.accept());
    await instructor.page.getByRole("button", { name: "Close exam" }).click();
    await expect(instructor.page.getByText("This exam is closed")).toBeVisible();

    await expect(async () => {
      await instructor.page.goto(`/admin/exams/${examId}/results`);
      await expect(instructor.page.getByRole("row", { name: /E2E Student/ })).toContainText("3"); // 3 of 3 correct
    }).toPass({ timeout: 60_000 });

    // Item analysis: one student, everyone got every question right -> 100% difficulty,
    // discrimination undefined (too few students for a meaningful top/bottom split).
    const itemRow = instructor.page.getByRole("row", { name: PROMPTS[0] });
    await expect(itemRow).toContainText("100%");
    await expect(itemRow).toContainText("too few students");

    await expect(async () => {
      await page.goto(`/exams/${examId}/results`);
      await expect(page.getByText("Total score")).toBeVisible();
      await expect(page.getByText("Questions answered").locator("xpath=following-sibling::dd[1]")).toHaveText("3");
      await expect(page.getByText("Total score").locator("xpath=following-sibling::dd[1]")).toHaveText("3");
    }).toPass({ timeout: 60_000 });

    // The student's dashboard now offers results, not "Start exam".
    await page.goto("/dashboard");
    await expect(page.getByTestId("my-exam").filter({ hasText: /E2E exam/ }).getByRole("link", { name: "View results" })).toBeVisible();

    // Audit trail: instructor can trace the student's timeline.
    await instructor.page.goto(`/admin/exams/${examId}/results`);
    await instructor.page.getByRole("button", { name: "Audit trail" }).click();
    await instructor.page.getByRole("link", { name: "View audit trail" }).click();
    await expect(instructor.page.getByText("answer_submitted").first()).toBeVisible();
    await expect(instructor.page.getByText(/submitted/).first()).toBeVisible();

    await instructor.context.close();
    await student.context.close();
  });

  test("server auto-submits a student who runs out of time and pushes time_up to their open page", async ({ browser }) => {
    const instructor = await newSession(browser);
    await login(instructor.page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);
    const { code } = await createExamWithCode(instructor.page, {
      title: `E2E timeout ${Date.now()}`,
      durationMinutes: 1,
      prompts: [PROMPTS[0]],
    });

    const student = await newSession(browser);
    await registerStudent(student.page, uniqueEmail("timeout"), "Timeout Student");
    const startResponse = student.page.waitForResponse((r) => /\/exams\/[0-9a-f-]{36}\/start$/.test(r.url()) && r.request().method() === "POST");
    await joinExam(student.page, code);
    const sessionId = (await (await startResponse).json()).session_id as string;

    await expect(student.page.getByRole("timer")).toContainText(/\d+:\d\d/);
    await expect(student.page.getByRole("group", { name: PROMPTS[0] })).toBeVisible();

    // Time-travel: the student "started" 5 minutes ago against a 1-minute exam.
    // Beat's sweep (every ~10s) auto-submits and publishes time_up over Redis to the open WebSocket.
    backdateSession(sessionId, 5);
    await expect(student.page.getByTestId("exam-ended")).toContainText(/Time is up/, { timeout: 60_000 });

    await instructor.context.close();
    await student.context.close();
  });

  test("a student cannot open an exam they are not enrolled in", async ({ browser }) => {
    const instructor = await newSession(browser);
    await login(instructor.page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);
    const { examId } = await createExamWithCode(instructor.page, { title: `E2E private ${Date.now()}`, durationMinutes: 30, prompts: [PROMPTS[0]] });

    const outsider = await newSession(browser);
    await registerStudent(outsider.page, uniqueEmail("outsider"), "Outsider");
    await outsider.page.goto(`/exams/${examId}`);
    await expect(outsider.page.getByText("Not enrolled in this exam")).toBeVisible();

    await instructor.context.close();
    await outsider.context.close();
  });
});
