import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "../api";
import { EntityPage } from "./Entities";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("master data management", () => {
  it("filters, edits and deactivates an entity through the API", async () => {
    const user = userEvent.setup();
    let items = [
      {
        id: 4,
        code: "NFS",
        name: "Northstar Fuel",
        active: true,
        email: "ops@example.com",
        phone: "+1 555 0100",
      },
    ];
    const get = vi.spyOn(api, "get").mockImplementation((path) => {
      if (path !== "/providers") throw new Error(`unexpected request: ${path}`);
      return Promise.resolve({
        data: { items, total: items.length, page: 1, pages: 1 },
      });
    });
    const put = vi.spyOn(api, "put").mockImplementation((_path, body) => {
      items = [{ ...items[0], ...body }];
      return Promise.resolve({ data: items[0] });
    });
    const remove = vi.spyOn(api, "delete").mockImplementation(() => {
      items = items.map((item) => ({ ...item, active: false }));
      return Promise.resolve({ data: null });
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <EntityPage
        type="providers"
        title="Fuel Providers"
        singular="Provider"
      />,
    );
    expect(await screen.findByText("Northstar Fuel")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Filter status"), "true");
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/providers", {
        params: { q: "", active: true, page: 1, page_size: 10 },
      }),
    );
    await user.type(screen.getByRole("textbox", { name: "Search" }), "north");
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/providers", {
        params: { q: "north", active: true, page: 1, page_size: 10 },
      }),
    );

    await user.click(
      screen.getByRole("button", { name: "Edit Northstar Fuel" }),
    );
    const name = screen.getByRole("textbox", { name: /^name/i });
    await user.clear(name);
    await user.type(name, "Northstar Fuel Services");
    await user.click(screen.getByRole("button", { name: "Save Provider" }));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith(
        "/providers/4",
        expect.objectContaining({
          name: "Northstar Fuel Services",
          active: true,
        }),
      ),
    );
    expect(
      await screen.findByText("Northstar Fuel Services"),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: "Deactivate Northstar Fuel Services",
      }),
    );
    await waitFor(() => expect(remove).toHaveBeenCalledWith("/providers/4"));
    expect(window.confirm).toHaveBeenCalledWith(
      "Deactivate Northstar Fuel Services? Historical invoices will be preserved.",
    );
  });
});
