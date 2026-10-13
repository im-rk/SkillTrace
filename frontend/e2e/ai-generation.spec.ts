import { expect, test } from "@playwright/test";
import { DEMO_PASSWORD, INSTRUCTOR_EMAIL, login, newSession } from "./helpers";

// The Groq call is intercepted in the browser, so this test is free, offline and deterministic.
// (The server-side parsing/validation of real model output is covered by the backend tests.)
test.describe("AI question generation (instructor review flow)", () => {
  test("instructor generates drafts, unticks one, and only the approved questions are saved", async ({ browser }) => {
    const { context, page } = await newSession(browser);
    await login(page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);
    await page.goto("/admin/questions");

    const unique = Date.now();
    // A throwaway skill: saved drafts must never pollute the seeded skills other journeys rely on.
    const skillName = `Throwaway ${unique}`;
    await page.getByLabel("New skill name").fill(skillName);
    await page.getByRole("button", { name: "Add skill" }).click();
    await expect(page.getByRole("option", { name: skillName }).first()).toBeAttached();
    const drafts = [
      { question_type: "true_false", prompt: `AI draft keep ${unique}`, difficulty: "easy", content: { correct_answer: true }, tags: ["ai-generated"] },
      { question_type: "true_false", prompt: `AI draft drop ${unique}`, difficulty: "easy", content: { correct_answer: false }, tags: ["ai-generated"] },
    ];
    await page.route("**/question-bank/generate", async (route) => {
      const body = route.request().postDataJSON();
      expect(body.count).toBe(2);
      expect(body.topic).toBe("equivalent fractions");
      await route.fulfill({ json: { drafts: drafts.map((d) => ({ ...d, skill_id: body.skill_id })), discarded: 1 } });
    });

    await page.getByLabel("Generate for skill").selectOption({ label: skillName });
    await page.getByLabel("How many (1–10)").fill("2");
    await page.getByLabel("Focus (optional)").fill("equivalent fractions");
    await page.getByRole("button", { name: "Generate with AI" }).click();

    const panel = page.getByTestId("ai-drafts");
    await expect(panel).toContainText(`AI draft keep ${unique}`);
    await expect(panel).toContainText("1 invalid draft discarded");

    // Nothing is saved yet.
    await page.getByRole("combobox").first().selectOption({ label: skillName });
    await expect(page.getByText(`AI draft keep ${unique}`, { exact: true })).toHaveCount(1); // only in the draft panel

    await panel.getByLabel(`AI draft drop ${unique}`).uncheck();
    await panel.getByRole("button", { name: "Save selected" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Saved 1 question" })).toBeVisible();

    // The approved draft is now a real question in the bank; the unticked one is not.
    await expect(page.getByText(`AI draft keep ${unique}`).first()).toBeVisible();
    await expect(page.getByText(`AI draft drop ${unique}`)).toHaveCount(0);

    await context.close();
  });

  test("a clear message is shown when AI generation is not configured", async ({ browser }) => {
    const { context, page } = await newSession(browser);
    await login(page, INSTRUCTOR_EMAIL, DEMO_PASSWORD);
    await page.goto("/admin/questions");
    await page.route("**/question-bank/generate", (route) =>
      route.fulfill({ status: 503, json: { detail: "AI question generation is not configured" } }),
    );
    await page.getByRole("button", { name: "Generate with AI" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "not configured" })).toBeVisible();
    await context.close();
  });
});
