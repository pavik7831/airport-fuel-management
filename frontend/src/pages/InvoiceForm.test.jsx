import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { api } from "../api";
import InvoiceForm from "./InvoiceForm";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("invoice form", () => {
  it("loads active accounts and submits draft inputs for server-side calculation", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/config")
        return Promise.resolve({
          data: { default_quantity_unit: "US_GALLON", default_currency: "USD" },
        });
      if (path === "/airlines")
        return Promise.resolve({
          data: {
            items: [{ id: 3, code: "ATL", name: "Atlas Air", active: true }],
          },
        });
      if (path === "/providers")
        return Promise.resolve({
          data: {
            items: [
              {
                id: 5,
                code: "NFS",
                name: "Northstar Fuel Services",
                active: true,
              },
            ],
          },
        });
      return Promise.reject(new Error(`unexpected request: ${path}`));
    });
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { id: 22, total_amount: "9750.00" } });

    render(
      <MemoryRouter initialEntries={["/invoices/new"]}>
        <Routes>
          <Route path="/invoices/new" element={<InvoiceForm />} />
          <Route path="/invoices/:id" element={<h1>Invoice created</h1>} />
        </Routes>
      </MemoryRouter>,
    );
    await user.type(
      await screen.findByLabelText(/invoice reference/i),
      "DEMO-001",
    );
    await user.selectOptions(await screen.findByLabelText(/^airline/i), "3");
    await user.selectOptions(screen.getByLabelText(/fuel provider/i), "5");
    await user.type(screen.getByLabelText(/fuel type/i), "JET A-1");
    await user.type(screen.getByLabelText(/quantity/i), "12500");
    await user.click(
      screen.getByRole("button", { name: /create draft invoice/i }),
    );

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(
      "/invoices",
      expect.objectContaining({
        reference: "DEMO-001",
        airline_id: 3,
        provider_id: 5,
        fuel_type: "JET A-1",
        quantity: 12500,
        tax_amount: 0,
      }),
    );
    expect(
      await screen.findByRole("heading", { name: "Invoice created" }),
    ).toBeInTheDocument();
  });

  it("shows configuration errors and keeps submit disabled without active accounts", async () => {
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/config")
        return Promise.reject({
          response: { data: { detail: "Configuration service unavailable" } },
        });
      if (path === "/airlines") return Promise.resolve({ data: { items: [] } });
      if (path === "/providers")
        return Promise.resolve({ data: { items: [] } });
      return Promise.reject(new Error(`unexpected request: ${path}`));
    });
    render(
      <MemoryRouter initialEntries={["/invoices/new"]}>
        <Routes>
          <Route path="/invoices/new" element={<InvoiceForm />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      await screen.findByText("Configuration service unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create draft invoice/i }),
    ).toBeDisabled();
  });
});
