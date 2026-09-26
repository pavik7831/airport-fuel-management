import { test, expect } from "@playwright/test";

test("login, configure fuel network, invoice billing, verify amount, and logout", async ({
  page,
}) => {
  const username = process.env.E2E_USERNAME;
  const password = process.env.E2E_PASSWORD;
  test.skip(
    !username || !password,
    "Set E2E_USERNAME and E2E_PASSWORD and run against a dedicated disposable test database.",
  );
  const suffix = `${Date.now()}`;
  const today = new Date().toISOString().slice(0, 10);
  await page.goto("/login");
  await page.getByLabel("Administrator username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(
    page.getByRole("heading", { name: /operations dashboard/i }),
  ).toBeVisible();

  await page.goto("/providers");
  await page.getByRole("button", { name: /add provider/i }).click();
  await page.locator('input[name="code"]').fill(`P${suffix}`);
  await page.locator('input[name="name"]').fill(`E2E Fuel Provider ${suffix}`);
  await page.getByRole("button", { name: /save provider/i }).click();
  await expect(page.getByText(`E2E Fuel Provider ${suffix}`)).toBeVisible();

  await page.goto("/airlines");
  await page.getByRole("button", { name: /add airline/i }).click();
  await page.locator('input[name="code"]').fill(`A${suffix}`);
  await page.locator('input[name="name"]').fill(`E2E Airline ${suffix}`);
  await page.getByRole("button", { name: /save airline/i }).click();
  await expect(page.getByText(`E2E Airline ${suffix}`)).toBeVisible();

  await page.goto("/rates");
  await page.getByRole("button", { name: /add rate/i }).click();
  const rateProvider = await page
    .locator('select[name="provider_id"] option')
    .filter({ hasText: `P${suffix}` })
    .getAttribute("value");
  await page.locator('select[name="provider_id"]').selectOption(rateProvider);
  await page.locator('input[name="fuel_type"]').fill("JET A-1");
  await page.locator('input[name="rate_per_unit"]').fill("2.5");
  await page.locator('input[name="effective_from"]').fill(today);
  await page.getByRole("button", { name: /save rate/i }).click();
  await expect(page.getByText("JET A-1").first()).toBeVisible();

  // Send the same new period at once. PostgreSQL's exclusion constraint must
  // allow one request and reject the other even if both API prechecks race.
  const rateProviderId = Number(rateProvider);
  const raceStatuses = await page.evaluate(
    async ({ rateProviderId, today }) => {
      const csrf = decodeURIComponent(
        document.cookie
          .split("; ")
          .find((item) => item.startsWith("afm_csrf="))
          .split("=")
          .slice(1)
          .join("="),
      );
      const payload = {
        provider_id: rateProviderId,
        fuel_type: "RACE TEST",
        rate_per_unit: "2.5",
        currency: "USD",
        effective_from: today,
        effective_to: null,
        active: true,
      };
      const send = () =>
        fetch("/api/v1/rates", {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
          },
          body: JSON.stringify(payload),
        }).then((response) => response.status);
      return Promise.all([send(), send()]);
    },
    { rateProviderId, today },
  );
  expect([...raceStatuses].sort()).toEqual([201, 409]);

  await page.goto("/invoices/new");
  await page.locator('input[name="reference"]').fill(`E2E-${suffix}`);
  await page.locator('input[name="invoice_date"]').fill(today);
  const invoiceAirline = await page
    .locator('select[name="airline_id"] option')
    .filter({ hasText: `A${suffix}` })
    .getAttribute("value");
  const invoiceProvider = await page
    .locator('select[name="provider_id"] option')
    .filter({ hasText: `P${suffix}` })
    .getAttribute("value");
  await page.locator('select[name="airline_id"]').selectOption(invoiceAirline);
  await page
    .locator('select[name="provider_id"]')
    .selectOption(invoiceProvider);
  await page.locator('input[name="billing_month"]').fill(today.slice(0, 7));
  await page.locator('input[name="fuel_type"]').fill("JET A-1");
  await page.locator('input[name="quantity"]').fill("100");
  await page.getByRole("button", { name: /create draft invoice/i }).click();
  await expect(
    page.getByRole("heading", { name: `E2E-${suffix}` }),
  ).toBeVisible();
  await expect(page.locator(".invoice-total .grand-total b")).toHaveText(
    "$250.00",
  );
  await expect(page.getByText("E2E Airline", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
});
