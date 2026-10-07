import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";
import { api } from "../api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("dashboard analytics", () => {
  it("requests the selected monthly date range from the API", async () => {
    const user = userEvent.setup();
    const get = vi.spyOn(api, "get").mockResolvedValue({
      data: {
        active_providers: 1,
        active_airlines: 1,
        active_rates: 1,
        total_invoices: 1,
        current_month_count: 0,
        current_month_amounts: [],
        monthly_totals: [],
        recent_invoices: [],
        provider_totals: [],
        airline_totals: [],
        outstanding_receivables: [],
      },
    });
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: /operations dashboard/i });
    await user.selectOptions(
      screen.getByLabelText(/monthly billing period/i),
      "6",
    );
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/dashboard", {
        params: { months: 6 },
      }),
    );
  });

  it("shows receivables grouped by currency without combining balances", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: {
        active_providers: 0,
        active_airlines: 0,
        active_rates: 0,
        total_invoices: 2,
        current_month_count: 0,
        current_month_amounts: [],
        monthly_totals: [],
        recent_invoices: [],
        provider_totals: [],
        airline_totals: [],
        outstanding_receivables: [
          { currency: "USD", balance_due: "150.00", invoice_count: 2 },
          { currency: "EUR", balance_due: "75.50", invoice_count: 1 },
        ],
      },
    });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Outstanding receivables" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/2 open invoices · USD/)).toBeInTheDocument();
    expect(screen.getByText("$150.00")).toBeInTheDocument();
    expect(screen.getByText(/1 open invoice · EUR/)).toBeInTheDocument();
    expect(screen.getByText("€75.50")).toBeInTheDocument();
  });
});
