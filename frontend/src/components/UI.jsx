import { Link } from "react-router-dom";
import { currency, pretty } from "../utils";

export function PageHeading({
  eyebrow = "OPERATIONS",
  title,
  subtitle,
  action,
}) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="muted mb-0">{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

export function ErrorBox({ error }) {
  return error ? (
    <div className="alert alert-danger">
      <i className="bi bi-exclamation-circle me-2" />
      {error}
    </div>
  ) : null;
}

export function Loading() {
  return (
    <div className="loading-panel">
      <span className="spinner-border spinner-border-sm text-primary me-2" />
      Loading records…
    </div>
  );
}

export function Empty({ title, detail }) {
  return (
    <div className="empty-state">
      <i className="bi bi-inbox" />
      <b>{title}</b>
      <span>{detail}</span>
    </div>
  );
}

export function Pager({ page, pages, onPage }) {
  return pages > 1 ? (
    <div className="pager">
      <span>
        Page {page} of {pages}
      </span>
      <div>
        <button
          className="btn btn-sm btn-outline-secondary"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          Previous
        </button>
        <button
          className="btn btn-sm btn-outline-secondary ms-2"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  ) : null;
}

export function InvoiceTable({ rows, compact = false }) {
  return (
    <div className="table-responsive">
      <table className="table align-middle">
        <thead>
          <tr>
            <th>REFERENCE</th>
            <th>AIRLINE / PROVIDER</th>
            <th>BILLING MONTH</th>
            <th>AMOUNT</th>
            <th>STATUS</th>
            {!compact && <th className="text-end">VIEW</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>
                <Link className="invoice-link" to={`/invoices/${r.id}`}>
                  {r.reference}
                </Link>
                <small className="cell-sub">
                  Invoice date · {r.invoice_date}
                </small>
              </td>
              <td>
                <b>{r.airline_name}</b>
                <small className="cell-sub">via {r.provider_name}</small>
              </td>
              <td>
                {new Date(`${r.billing_month}T00:00:00`).toLocaleString(
                  undefined,
                  { month: "long", year: "numeric" },
                )}
              </td>
              <td>
                <b>{currency(r.total_amount, r.currency)}</b>
                <small className="cell-sub">
                  {Number(r.quantity).toLocaleString()} units · {r.fuel_type}
                </small>
              </td>
              <td>
                <span className={`state state-${r.status.toLowerCase()}`}>
                  {pretty(r.status)}
                </span>
              </td>
              {!compact && (
                <td className="text-end">
                  <Link
                    className="btn btn-sm btn-light"
                    to={`/invoices/${r.id}`}
                    aria-label="View invoice"
                  >
                    <i className="bi bi-arrow-up-right" />
                  </Link>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
