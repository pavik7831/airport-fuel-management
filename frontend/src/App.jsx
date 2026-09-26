import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { api, errorMessage } from "./api";
const Dashboard = lazy(() => import("./pages/Dashboard"));
const EntityPage = lazy(() => import("./pages/Entities"));
const Rates = lazy(() => import("./pages/Rates"));
const Invoices = lazy(() => import("./pages/Invoices"));
const InvoiceForm = lazy(() => import("./pages/InvoiceForm"));
const InvoiceDetail = lazy(() => import("./pages/InvoiceDetail"));

const nav = [
  ["Dashboard", "/", "bi-grid-1x2"],
  ["Fuel providers", "/providers", "bi-fuel-pump"],
  ["Airlines", "/airlines", "bi-airplane"],
  ["Fuel rates", "/rates", "bi-tags"],
  ["Invoices", "/invoices", "bi-receipt"],
];

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const loc = useLocation();
  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
    const unauth = () => setUser(null);
    window.addEventListener("afm:unauthorized", unauth);
    return () => window.removeEventListener("afm:unauthorized", unauth);
  }, [refresh]);
  if (loading)
    return (
      <div className="screen-center">
        <span className="spinner-border text-primary" />
      </div>
    );
  return (
    <Suspense
      fallback={
        <div className="screen-center" role="status">
          <span className="spinner-border text-primary" />
          <span className="visually-hidden">Loading page</span>
        </div>
      }
    >
      <Routes>
        <Route
          path="/login"
          element={
            user ? <Navigate to="/" replace /> : <Login onLogin={refresh} />
          }
        />
        <Route
          path="*"
          element={
            user ? (
              <Shell user={user} setUser={setUser} key={loc.pathname} />
            ) : (
              <Navigate to="/login" replace state={{ from: loc }} />
            )
          }
        />
      </Routes>
    </Suspense>
  );
}

function Login({ onLogin }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const go = useNavigate();
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      await api.post("/auth/login", {
        username: f.get("username"),
        password: f.get("password"),
      });
      await onLogin();
      go("/", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-bg">
      <div className="login-card">
        <div className="brand-mark">
          <i className="bi bi-fuel-pump-fill" />
        </div>
        <p className="eyebrow">OPERATIONS PLATFORM</p>
        <h1>
          Airport Fuel
          <br />
          Management
        </h1>
        <p className="muted">
          Sign in to manage fueling and billing operations.
        </p>
        <form onSubmit={submit} className="vstack gap-3 mt-4">
          <label>
            Administrator username
            <input
              name="username"
              className="form-control"
              autoComplete="username"
              required
              autoFocus
            />
          </label>
          <label>
            Password
            <input
              name="password"
              className="form-control"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          {error && <div className="alert alert-danger py-2">{error}</div>}
          <button className="btn btn-primary btn-lg" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}{" "}
            <i className="bi bi-arrow-right ms-2" />
          </button>
        </form>
        <div className="login-foot">SECURE ADMINISTRATOR ACCESS</div>
      </div>
    </main>
  );
}

function Shell({ user, setUser }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const go = useNavigate();
  async function logout() {
    try {
      await api.post("/auth/logout");
    } finally {
      setUser(null);
      go("/login");
    }
  }
  const title =
    nav.find((x) => x[1] === loc.pathname)?.[0] || "Invoice details";
  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark small">
            <i className="bi bi-fuel-pump-fill" />
          </div>
          <div>
            <b>AFM</b>
            <small>FUEL OPERATIONS</small>
          </div>
          <button
            className="btn btn-link d-lg-none ms-auto text-white"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
          >
            <i className="bi bi-x-lg" />
          </button>
        </div>
        <div className="side-label">WORKSPACE</div>
        <nav>
          {nav.map(([name, path, icon]) => (
            <Link
              key={path}
              onClick={() => setOpen(false)}
              className={`nav-entry ${loc.pathname === path ? "active" : ""}`}
              to={path}
            >
              <i className={`bi ${icon}`} />
              <span>{name}</span>
              {path === "/invoices" && (
                <i className="bi bi-chevron-right ms-auto tiny" />
              )}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="status-pill">
            <span /> SYSTEM OPERATIONAL
          </div>
          <div className="sidebar-version">
            AIRPORT FUEL MANAGEMENT <span>v1.0</span>
          </div>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <button
            className="btn menu-toggle d-lg-none"
            onClick={() => setOpen(!open)}
            aria-label="Open menu"
          >
            <i className="bi bi-list" />
          </button>
          <div className="crumb">
            <span>Workspace</span>
            <i className="bi bi-chevron-right" />
            {title}
          </div>
          <div className="top-actions">
            <span className="today-label">OPERATIONS CONSOLE</span>
            <div className="top-divider" />
            <div className="profile">
              <div className="avatar">
                {user.username.slice(0, 1).toUpperCase()}
              </div>
              <div className="d-none d-sm-block">
                <b>{user.username}</b>
                <small>Administrator</small>
              </div>
              <button
                className="btn btn-link text-secondary p-1"
                onClick={logout}
                title="Sign out"
                aria-label="Sign out"
              >
                <i className="bi bi-box-arrow-right" />
              </button>
            </div>
          </div>
        </header>
        <main className="page-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route
              path="/providers"
              element={
                <EntityPage
                  type="providers"
                  title="Fuel providers"
                  singular="Provider"
                />
              }
            />
            <Route
              path="/airlines"
              element={
                <EntityPage
                  type="airlines"
                  title="Airlines"
                  singular="Airline"
                />
              }
            />
            <Route path="/rates" element={<Rates />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/invoices/new" element={<InvoiceForm />} />
            <Route path="/invoices/:id/edit" element={<InvoiceForm />} />
            <Route path="/invoices/:id" element={<InvoiceDetail />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <footer className="app-footer">
          <span>© {new Date().getFullYear()} Airport Fuel Management</span>
          <span>All amounts shown in invoice currency</span>
        </footer>
      </div>
      {open && (
        <button
          className="backdrop d-lg-none"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        />
      )}
    </div>
  );
}

export default App;
