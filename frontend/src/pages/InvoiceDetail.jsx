import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { ErrorBox, Loading, PageHeading } from "../components/UI";
import { currency, pretty } from "../utils";

export function InvoiceDetail() {
  const { id } = useParams(),
    [row, setRow] = useState(null),
    [error, setError] = useState("");
  const load = useCallback(
    () =>
      api
        .get(`/invoices/${id}`)
        .then((r) => setRow(r.data))
        .catch((e) => setError(errorMessage(e))),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);
  async function transition(action) {
    try {
      if (action === "cancel") {
        const reason = window.prompt("Enter a cancellation reason (required):");
        if (!reason || reason.trim().length < 3) return;
        await api.post(`/invoices/${id}/cancel`, { reason });
      } else await api.post(`/invoices/${id}/finalize`);
      load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  if (error)
    return (
      <>
        <PageHeading eyebrow="INVOICE DETAILS" title="Invoice" />
        <ErrorBox error={error} />
      </>
    );
  if (!row) return <Loading />;
  return (
    <>
      <PageHeading
        eyebrow="BILLING / INVOICE DETAILS"
        title={row.reference}
        subtitle="Historical rate and billing information is preserved on this invoice."
        action={
          <>
            {row.status === "DRAFT" && (
              <Link
                to={`/invoices/${id}/edit`}
                className="btn btn-primary me-2"
              >
                <i className="bi bi-pencil me-2" />
                Edit draft
              </Link>
            )}
            <button
              onClick={() => window.print()}
              className="btn btn-outline-secondary me-2"
            >
              <i className="bi bi-printer me-2" />
              Print
            </button>
            <Link to="/invoices" className="btn btn-light">
              Back to invoices
            </Link>
          </>
        }
      />
      <ErrorBox error={error} />
      <div className="invoice-paper">
        <div className="invoice-paper-head">
          <div>
            <div className="brand-mark small">
              <i className="bi bi-fuel-pump-fill" />
            </div>
            <span className="eyebrow">AIRPORT FUEL MANAGEMENT</span>
            <h2>Fuel invoice</h2>
          </div>
          <span className={`state state-${row.status.toLowerCase()}`}>
            {pretty(row.status)}
          </span>
        </div>
        <div className="invoice-meta">
          <div>
            <span>INVOICE REFERENCE</span>
            <b>{row.reference}</b>
          </div>
          <div>
            <span>INVOICE DATE</span>
            <b>{row.invoice_date}</b>
          </div>
          <div>
            <span>BILLING PERIOD</span>
            <b>
              {new Date(`${row.billing_month}T00:00:00`).toLocaleString(
                undefined,
                { month: "long", year: "numeric" },
              )}
            </b>
          </div>
        </div>
        <div className="invoice-parties">
          <div>
            <span>BILLED TO AIRLINE</span>
            <b>{row.airline_name}</b>
            <small>{row.airline_code}</small>
          </div>
          <div>
            <span>FUEL PROVIDER</span>
            <b>{row.provider_name}</b>
            <small>{row.provider_code}</small>
          </div>
        </div>
        <div className="table-responsive">
          <table className="table invoice-lines">
            <thead>
              <tr>
                <th>FUEL / SERVICE</th>
                <th className="text-end">QUANTITY</th>
                <th className="text-end">RATE / UNIT</th>
                <th className="text-end">AMOUNT</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <b>{row.fuel_type}</b>
                  <small className="cell-sub">
                    Fuel supply · {row.currency}
                  </small>
                </td>
                <td className="text-end">
                  {Number(row.quantity).toLocaleString()}
                </td>
                <td className="text-end">
                  {currency(row.rate_per_unit, row.currency)}
                </td>
                <td className="text-end">
                  <b>{currency(row.subtotal, row.currency)}</b>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="invoice-total">
          <div>
            <span>Subtotal</span>
            <b>{currency(row.subtotal, row.currency)}</b>
          </div>
          <div>
            <span>Tax</span>
            <b>{currency(row.tax_amount, row.currency)}</b>
          </div>
          <div className="grand-total">
            <span>Total due</span>
            <b>{currency(row.total_amount, row.currency)}</b>
          </div>
        </div>
        {row.notes && (
          <div className="invoice-notes">
            <span>NOTES</span>
            <p>{row.notes}</p>
          </div>
        )}
        {row.cancel_reason && (
          <div className="alert alert-warning">
            Cancellation reason: {row.cancel_reason}
          </div>
        )}
        {row.status === "DRAFT" && (
          <div className="invoice-actions no-print">
            <button
              className="btn btn-primary"
              onClick={() => transition("finalize")}
            >
              Finalize invoice
            </button>
            <button
              className="btn btn-outline-danger"
              onClick={() => transition("cancel")}
            >
              Cancel invoice
            </button>
            <span>Finalized and cancelled invoices are locked.</span>
          </div>
        )}
      </div>
    </>
  );
}
export default InvoiceDetail;
