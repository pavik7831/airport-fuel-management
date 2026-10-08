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
  vi.unstubAllGlobals();
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
      expect(get).toHaveBeenLastCalledWith(
        "/invoices",
        expect.objectContaining({
          params: {
            q: "MAY-26",
            airline_id: "3",
            provider_id: "5",
            billing_month: "2026-05-01",
            status: "FINALIZED",
            page: 1,
            page_size: 10,
          },
          signal: expect.objectContaining({ aborted: false }),
        }),
      ),
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

  it("shows filter-specific empty guidance and clears all invoice filters", async () => {
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
    await screen.findByText("Create an invoice to start monthly billing.");
    await user.type(screen.getByLabelText("Search invoice reference"), "INV-1");
    await user.selectOptions(screen.getByLabelText("Filter airline"), "3");
    await user.selectOptions(screen.getByLabelText("Filter provider"), "5");
    fireEvent.change(screen.getByLabelText("Filter billing month"), {
      target: { value: "2026-05" },
    });
    await user.selectOptions(screen.getByLabelText("Filter status"), "DRAFT");

    expect(
      await screen.findByText(
        "Try adjusting or clearing the filters to see more invoices.",
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /clear filters/i }));

    expect(screen.getByLabelText("Search invoice reference")).toHaveValue("");
    expect(screen.getByLabelText("Filter airline")).toHaveValue("");
    expect(screen.getByLabelText("Filter provider")).toHaveValue("");
    expect(screen.getByLabelText("Filter billing month")).toHaveValue("");
    expect(screen.getByLabelText("Filter status")).toHaveValue("");
    expect(
      await screen.findByText("Create an invoice to start monthly billing."),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith(
        "/invoices",
        expect.objectContaining({
          params: {
            q: "",
            airline_id: undefined,
            provider_id: undefined,
            billing_month: undefined,
            status: undefined,
            page: 1,
            page_size: 10,
          },
          signal: expect.objectContaining({ aborted: false }),
        }),
      ),
    );
    expect(
      screen.queryByRole("button", { name: /clear filters/i }),
    ).not.toBeInTheDocument();
  });

  it("exports only the invoices matching the active filters", async () => {
    const user = userEvent.setup();
    vi.spyOn(window.HTMLAnchorElement.prototype, "click").mockImplementation(
      () => {},
    );
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:invoices"),
      revokeObjectURL: vi.fn(),
    });
    const get = vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/airlines" || path === "/providers")
        return Promise.resolve({ data: { items: [] } });
      if (path === "/invoices") return Promise.resolve({ data: page });
      if (path === "/invoices/export.csv")
        return Promise.resolve({ data: new Blob(["reference\nINV-1"]) });
      throw new Error(`unexpected request: ${path}`);
    });

    render(
      <MemoryRouter>
        <Invoices />
      </MemoryRouter>,
    );
    await screen.findByText("No invoices found");
    await user.type(screen.getByLabelText("Search invoice reference"), "INV-1");
    await user.selectOptions(screen.getByLabelText("Filter status"), "DRAFT");
    await user.click(screen.getByRole("button", { name: "Export CSV" }));

    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/invoices/export.csv", {
        params: {
          q: "INV-1",
          airline_id: undefined,
          provider_id: undefined,
          billing_month: undefined,
          status: "DRAFT",
        },
        responseType: "blob",
      }),
    );
  });
});
