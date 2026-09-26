import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Rates from "./Rates";
import { api } from "../api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("fuel rates", () => {
  it("creates a provider-linked rate and refreshes the rate list", async () => {
    const user = userEvent.setup();
    const rates = [];
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/rates")
        return Promise.resolve({
          data: { items: rates, total: rates.length, page: 1, pages: 1 },
        });
      if (path === "/config")
        return Promise.resolve({ data: { default_currency: "USD" } });
      if (path === "/providers")
        return Promise.resolve({
          data: {
            items: [
              {
                id: 7,
                code: "NFS",
                name: "Northstar Fuel Services",
                active: true,
              },
            ],
          },
        });
      return Promise.reject(new Error(`unexpected request: ${path}`));
    });
    const post = vi.spyOn(api, "post").mockImplementation((path, body) => {
      if (path !== "/rates")
        return Promise.reject(new Error("unexpected post"));
      rates.push({
        id: 1,
        ...body,
        created_at: new Date().toISOString(),
      });
      return Promise.resolve({ data: rates[0] });
    });
    render(<Rates />);
    await user.click(await screen.findByRole("button", { name: /add rate/i }));
    await user.selectOptions(screen.getByLabelText(/^provider$/i), "7");
    await user.type(screen.getByPlaceholderText("JET A-1"), "JET A-1");
    await user.type(screen.getByLabelText(/rate \/ unit/i), "0.78");
    fireEvent.change(screen.getByLabelText(/effective from/i), {
      target: { value: "2026-01-01" },
    });
    await user.click(screen.getByRole("button", { name: /save rate/i }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(
      "/rates",
      expect.objectContaining({
        provider_id: 7,
        fuel_type: "JET A-1",
        rate_per_unit: 0.78,
        currency: "USD",
        effective_from: "2026-01-01",
        active: true,
      }),
    );
    expect(await screen.findByText("JET A-1")).toBeInTheDocument();
  });
});
