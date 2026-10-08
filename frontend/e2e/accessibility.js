import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";

export async function expectWcag21AA(page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  expect(results.violations).toEqual([]);
}
