import { expect, test } from "@playwright/test";
import { expectWcag21AA } from "./accessibility";

test("administrator sign-in page has no WCAG 2.1 A/AA axe violations", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Unauthorized" }),
    }),
  );
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: /airport fuel management/i }),
  ).toBeVisible();
  await expectWcag21AA(page);
});

test("authenticated dashboard has no WCAG 2.1 A/AA axe violations", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: 1, username: "accessibility-test" }),
    }),
  );
  await page.route("**/api/v1/dashboard**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        active_providers: 1,
        active_airlines: 1,
        active_rates: 1,
        total_invoices: 0,
        current_month_count: 0,
        current_month_amounts: [],
        monthly_totals: [],
        recent_invoices: [],
        provider_totals: [],
        airline_totals: [],
        outstanding_receivables: [],
      }),
    }),
  );

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /operations dashboard/i }),
  ).toBeVisible();
  await expectWcag21AA(page);
});
