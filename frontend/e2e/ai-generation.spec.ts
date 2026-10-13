import { expect, test, type Page } from "@playwright/test";
import { DEMO_PASSWORD, INSTRUCTOR_EMAIL, login, newSession } from "./helpers";

// The Groq call is intercepted in the browser, so these tests are free, offline and deterministic.
// (Server-side parsing and validation of real model output is covered by the backend tests.)

async function openNewSkill(page: Page, name: string) {
  await page.goto("/admin/skills");
  await page.getByRole("button", { name: "New skill" }).click();
  await page.getByLabel("Skill name").fill(name);
  await page.getByRole("button", { name: "Create skill" }).click();
  await expect(page).toHaveURL(/\/admin\/skills\/[0-9a-f-]{36}$/);
}

test.describe("AI question drafting (instructor review flow)", () => {
  test("instructor drafts questions, unticks one, and only the approved ones are saved", async ({ browser }) => {
    const { context, page } = await newSession(browser);
    await login(page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);

    // A throwaway skill: saved drafts must never pollute the seeded skills other journeys rely on.
    const unique = Date.now();
    await openNewSkill(page, `Throwaway ${unique}`);

    const drafts = [
      { question_type: "true_false", prompt: `AI draft keep ${unique}`, difficulty: "easy", content: { correct_answer: true }, tags: ["ai-generated"] },
      { question_type: "true_false", prompt: `AI draft drop ${unique}`, difficulty: "easy", content: { correct_answer: false }, tags: ["ai-generated"] },
    ];
    await page.route("**/question-bank/generate", async (route) => {
      const body = route.request().postDataJSON();
      expect(body.count).toBe(3);
      expect(body.topic).toBe("equivalent fractions");
      await route.fulfill({ json: { drafts: drafts.map((d) => ({ ...d, skill_id: body.skill_id })), discarded: 1 } });
    });

    await page.getByRole("button", { name: "Draft with AI" }).click();
    await page.getByLabel("How many questions").selectOption("3");
    await page.getByLabel("Focus (optional)").fill("equivalent fractions");
    await page.getByRole("button", { name: "Draft questions" }).click();

    const panel = page.getByTestId("ai-drafts");
    await expect(panel).toContainText(`AI draft keep ${unique}`);
    await expect(panel).toContainText("1 invalid draft was thrown away");
    await expect(page.getByTestId("question-row")).toHaveCount(0); // nothing is saved yet

    await panel.getByLabel(`AI draft drop ${unique}`).uncheck();
    await panel.getByRole("button", { name: "Save selected" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Saved 1 question" })).toBeVisible();

    // The approved draft is now a real question, marked as AI-drafted; the unticked one is not.
    const rows = page.getByTestId("question-row");
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText(`AI draft keep ${unique}`);
    await expect(rows.first()).toContainText("AI-drafted");

    await context.close();
  });

  test("a clear message is shown when AI drafting is not switched on", async ({ browser }) => {
    const { context, page } = await newSession(browser);
    await login(page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);
    await openNewSkill(page, `Throwaway ${Date.now()}`);
    await page.route("**/question-bank/generate", (route) => route.fulfill({ status: 503, json: { detail: "AI question generation is not configured" } }));
    await page.getByRole("button", { name: "Draft with AI" }).click();
    await page.getByRole("button", { name: "Draft questions" }).click();
    await expect(page.getByText(/not switched on/)).toBeVisible();
    await context.close();
  });
});
