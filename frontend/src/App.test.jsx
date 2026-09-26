import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import App from "./App.jsx";
import { api } from "./api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AFM authentication shell", () => {
  it("shows the sign-in screen when no administrator session exists", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new Error("unauthorized"));
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );
    expect(
      await screen.findByRole("heading", { name: /airport fuel management/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
  });

  it("renders dashboard data from the API for an authenticated admin", async () => {
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/auth/me")
        return Promise.resolve({ data: { id: 1, username: "operator" } });
      if (path === "/dashboard")
        return Promise.resolve({
          data: {
            active_providers: 3,
            active_airlines: 4,
            active_rates: 5,
            total_invoices: 6,
            current_month_count: 0,
            current_month_amounts: [],
            monthly_totals: [],
            recent_invoices: [],
            provider_totals: [],
            airline_totals: [],
          },
        });
      return Promise.reject(new Error("unexpected request"));
    });
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );
    expect(
      await screen.findByRole("heading", { name: /operations dashboard/i }),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("6")).toBeInTheDocument());
  });

  it("submits credentials, refreshes the session, and opens the dashboard", async () => {
    const user = userEvent.setup();
    const dashboard = {
      active_providers: 1,
      active_airlines: 1,
      active_rates: 1,
      total_invoices: 0,
      current_month_count: 0,
      current_month_amounts: [],
      monthly_totals: [],
      recent_invoices: [],
      provider_totals: [],
      airline_totals: [],
    };
    let sessionChecks = 0;
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/auth/me") {
        sessionChecks += 1;
        return sessionChecks === 1
          ? Promise.reject(new Error("no session"))
          : Promise.resolve({ data: { id: 1, username: "operator" } });
      }
      if (path === "/dashboard") return Promise.resolve({ data: dashboard });
      return Promise.reject(new Error(`unexpected request: ${path}`));
    });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <App />
      </MemoryRouter>,
    );
    await user.type(
      await screen.findByLabelText(/administrator username/i),
      "operator",
    );
    await user.type(screen.getByLabelText(/password/i), "a-long-test-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(post).toHaveBeenCalledWith("/auth/login", {
      username: "operator",
      password: "a-long-test-password",
    });
    expect(
      await screen.findByRole("heading", { name: /operations dashboard/i }),
    ).toBeInTheDocument();
  });

  it("shows server login errors and logs out an authenticated administrator", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "get").mockRejectedValue(new Error("no session"));
    vi.spyOn(api, "post").mockRejectedValue({
      response: { data: { detail: "Invalid username or password" } },
    });
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <App />
      </MemoryRouter>,
    );
    await user.type(
      await screen.findByLabelText(/administrator username/i),
      "operator",
    );
    await user.type(screen.getByLabelText(/password/i), "wrong-password-value");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(
      await screen.findByText("Invalid username or password"),
    ).toBeInTheDocument();

    vi.restoreAllMocks();
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/auth/me")
        return Promise.resolve({ data: { id: 1, username: "operator" } });
      if (path === "/dashboard")
        return Promise.resolve({
          data: {
            active_providers: 0,
            active_airlines: 0,
            active_rates: 0,
            total_invoices: 0,
            current_month_count: 0,
            current_month_amounts: [],
            monthly_totals: [],
            recent_invoices: [],
            provider_totals: [],
            airline_totals: [],
          },
        });
      return Promise.reject(new Error("unexpected request"));
    });
    const logout = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    cleanup();
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    await user.click(await screen.findByRole("button", { name: /sign out/i }));
    expect(logout).toHaveBeenCalledWith("/auth/logout");
    expect(
      await screen.findByRole("heading", { name: /airport fuel management/i }),
    ).toBeInTheDocument();
  });

  it("creates a provider through the API and reloads the provider table", async () => {
    const user = userEvent.setup();
    const providers = [];
    const dashboard = {
      active_providers: 0,
      active_airlines: 0,
      active_rates: 0,
      total_invoices: 0,
      current_month_count: 0,
      current_month_amounts: [],
      monthly_totals: [],
      recent_invoices: [],
      provider_totals: [],
      airline_totals: [],
    };
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/auth/me")
        return Promise.resolve({ data: { id: 1, username: "operator" } });
      if (path === "/dashboard") return Promise.resolve({ data: dashboard });
      if (path === "/providers")
        return Promise.resolve({
          data: {
            items: providers,
            total: providers.length,
            page: 1,
            pages: 1,
          },
        });
      return Promise.reject(new Error(`unexpected request: ${path}`));
    });
    const post = vi.spyOn(api, "post").mockImplementation((path, body) => {
      if (path !== "/providers")
        return Promise.reject(new Error("unexpected post"));
      providers.push({
        id: 1,
        ...body,
        email: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      return Promise.resolve({ data: providers[0] });
    });
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    await user.click(
      await screen.findByRole("link", { name: /fuel providers/i }),
    );
    await user.click(
      await screen.findByRole("button", { name: /add provider/i }),
    );
    await user.type(screen.getByLabelText(/provider code/i), "DEMO-FUEL");
    await user.type(screen.getByLabelText(/^name/i), "Demo Fuel Co");
    await user.click(screen.getByRole("button", { name: /save provider/i }));
    expect(post).toHaveBeenCalledWith(
      "/providers",
      expect.objectContaining({
        code: "DEMO-FUEL",
        name: "Demo Fuel Co",
        active: true,
      }),
    );
    expect(await screen.findByText("Demo Fuel Co")).toBeInTheDocument();
  });
});
