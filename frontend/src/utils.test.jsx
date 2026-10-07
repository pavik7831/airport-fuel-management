import { describe, expect, it } from "vitest";
import { currency, pretty } from "./utils";

describe("currency", () => {
  it("formats numeric strings in the requested currency", () => {
    expect(currency("1234.5", "USD")).toBe(
      new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: "USD",
      }).format(1234.5),
    );
  });

  it("treats missing amounts as zero", () => {
    expect(currency(null, "USD")).toBe(
      new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: "USD",
      }).format(0),
    );
  });
});

describe("pretty", () => {
  it("converts underscore-separated statuses to title case", () => {
    expect(pretty("partially_paid")).toBe("Partially Paid");
  });
});
