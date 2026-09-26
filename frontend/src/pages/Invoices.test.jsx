import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { api } from "../api";
import { Invoices } from "./Invoices";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const page = { items: [], total: 0, page: 1, pages: 0 };

describe("invoice list integration", () => {
  it("applies billing filters to the invoice API and resets pagination", async () => {
    const user = userEvent.setup();
    const get = vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/airlines")
        return Promise.resolve({
          data: { items: [{ id: 3, code: "ATL", name: "Atlas Air" }] },
        });
      if (path === "/providers")
        return Promise.resolve({
          data: { items: [{ id: 5, code: "NFS", name: "Northstar Fuel" }] },
        });
      if (path === "/invoices") return Promise.resolve({ data: page });
      throw new Error(`unexpected request: ${path}`);
    });

    render(
      <MemoryRouter>
        <Invoices />
      </MemoryRouter>,
    );
    await screen.findByText("No invoices found");
    await user.type(
      screen.getByLabelText("Search invoice reference"),
      "MAY-26",
    );
    await user.selectOptions(screen.getByLabelText("Filter airline"), "3");
    await user.selectOptions(screen.getByLabelText("Filter provider"), "5");
    fireEvent.change(screen.getByLabelText("Filter billing month"), {
      target: { value: "2026-05" },
    });
    await user.selectOptions(
      screen.getByLabelText("Filter status"),
      "FINALIZED",
    );

    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/invoices", {
        params: {
          q: "MAY-26",
          airline_id: "3",
          provider_id: "5",
          billing_month: "2026-05-01",
          status: "FINALIZED",
          page: 1,
          page_size: 10,
        },
      }),
    );
  });

  it("shows invoice API failures with an actionable message", async () => {
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/airlines" || path === "/providers")
        return Promise.resolve({ data: { items: [] } });
      if (path === "/invoices")
        return Promise.reject({
          response: { data: { detail: "Billing API unavailable" } },
        });
      throw new Error(`unexpected request: ${path}`);
    });
    render(
      <MemoryRouter>
        <Invoices />
      </MemoryRouter>,
    );
    expect(
      await screen.findByText("Billing API unavailable"),
    ).toBeInTheDocument();
  });
});
