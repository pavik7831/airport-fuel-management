import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { api } from "../api";
import { InvoiceDetail } from "./InvoiceDetail";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const invoice = {
  id: 7,
  reference: "INV-7",
  invoice_date: "2026-10-01",
  due_date: "2026-10-31",
  billing_month: "2026-10-01",
  airline_name: "North Air",
  airline_code: "NORTH",
  provider_name: "Fuel Co",
  provider_code: "FUEL",
  fuel_type: "JET A-1",
  quantity: "10.000",
  rate_per_unit: "10.00000",
  currency: "USD",
  subtotal: "100.00",
  tax_amount: "0.00",
  total_amount: "100.00",
  paid_amount: "0.00",
  balance_due: "100.00",
  payment_status: "UNPAID",
  status: "FINALIZED",
  payments: [],
};

describe("invoice payment recording", () => {
  it("records a partial payment and refreshes the outstanding balance", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "get").mockResolvedValue({ data: invoice });
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        ...invoice,
        paid_amount: "40.00",
        balance_due: "60.00",
        payment_status: "PARTIALLY_PAID",
        payments: [
          {
            id: 1,
            amount: "40.00",
            payment_date: "2026-10-05",
            reference: "WIRE-42",
            notes: "First installment",
          },
        ],
      },
    });

    render(
      <MemoryRouter initialEntries={["/invoices/7"]}>
        <Routes>
          <Route path="/invoices/:id" element={<InvoiceDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByText("No payments recorded yet.");
    expect(screen.getByText("2026-10-31")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Payment amount/), "40.00");
    await user.type(screen.getByLabelText("Payment reference"), "WIRE-42");
    await user.type(screen.getByLabelText("Notes"), "First installment");
    await user.click(screen.getByRole("button", { name: "Record payment" }));

    expect(post).toHaveBeenCalledWith("/invoices/7/payments", {
      amount: "40",
      payment_date: expect.any(String),
      reference: "WIRE-42",
      notes: "First installment",
    });
    expect(await screen.findByText(/PARTIALLY PAID/)).toBeInTheDocument();
    expect(
      screen.getByText("Outstanding balance").nextSibling,
    ).toHaveTextContent("$60.00");
    expect(screen.getByText("WIRE-42")).toBeInTheDocument();
  });

  it("keeps invoice details and form values visible when payment recording fails", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "get").mockResolvedValue({ data: invoice });
    vi.spyOn(api, "post").mockRejectedValue({
      response: { data: { detail: "Payment exceeds the remaining balance" } },
    });

    render(
      <MemoryRouter initialEntries={["/invoices/7"]}>
        <Routes>
          <Route path="/invoices/:id" element={<InvoiceDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByText("No payments recorded yet.");
    const amount = screen.getByLabelText(/Payment amount/);
    await user.type(amount, "40");
    await user.click(screen.getByRole("button", { name: "Record payment" }));

    expect(
      await screen.findByText("Payment exceeds the remaining balance"),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "INV-7" })).toBeInTheDocument();
    expect(amount).toHaveValue(40);
  });
});
