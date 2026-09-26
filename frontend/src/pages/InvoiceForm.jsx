import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { ErrorBox, PageHeading } from "../components/UI";

export function InvoiceForm() {
  const { id } = useParams();
  const [initial, setInitial] = useState(null),
    [quantityUnit, setQuantityUnit] = useState("US GALLON"),
    [airlines, setAirlines] = useState([]),
    [providers, setProviders] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const go = useNavigate();
  useEffect(() => {
    api
      .get("/config")
      .then((r) =>
        setQuantityUnit(r.data.default_quantity_unit.replaceAll("_", " ")),
      )
      .catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(() => {
    const requests = [
      api.get("/airlines", { params: { active: true, page_size: 100 } }),
      api.get("/providers", { params: { active: true, page_size: 100 } }),
    ];
    if (id) requests.push(api.get(`/invoices/${id}`));
    Promise.all(requests)
      .then(([a, p, invoice]) => {
        setAirlines(a.data.items);
        setProviders(p.data.items);
        if (invoice) {
          if (invoice.data.status !== "DRAFT")
            throw new Error("Only draft invoices can be edited");
          setInitial(invoice.data);
        }
      })
      .catch((e) => setError(errorMessage(e)));
  }, [id]);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    const f = new FormData(e.currentTarget),
      d = Object.fromEntries(f);
    d.airline_id = Number(d.airline_id);
    d.provider_id = Number(d.provider_id);
    d.quantity = Number(d.quantity);
    d.tax_amount = Number(d.tax_amount || 0);
    d.billing_month = `${d.billing_month}-01`;
    try {
      const { data } = id
        ? await api.put(`/invoices/${id}`, d)
        : await api.post("/invoices", d);
      go(`/invoices/${data.id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  const value = (key, fallback = "") => initial?.[key] ?? fallback;
  return (
    <>
      <PageHeading
        eyebrow={id ? "BILLING / EDIT DRAFT" : "BILLING / NEW INVOICE"}
        title={id ? "Edit draft invoice" : "Create invoice"}
        subtitle="The server selects the applicable rate and calculates all amounts."
      />
      <ErrorBox error={error} />
      <div className="panel form-panel invoice-form-panel">
        <div className="form-note">
          <i className="bi bi-shield-check" />
          <span>
            Invoice totals are calculated by the server using the effective rate
            for the invoice date. Tax defaults to zero.
          </span>
        </div>
        <form onSubmit={submit} className="form-grid">
          <label>
            Invoice reference *
            <input
              className="form-control"
              name="reference"
              maxLength="40"
              placeholder="INV-2026-0001"
              required
              defaultValue={value("reference")}
            />
          </label>
          <label>
            Invoice date *
            <input
              className="form-control"
              type="date"
              name="invoice_date"
              required
              defaultValue={value(
                "invoice_date",
                new Date().toISOString().slice(0, 10),
              )}
            />
          </label>
          <label>
            Airline *
            <select
              className="form-select"
              name="airline_id"
              required
              defaultValue={value("airline_id")}
            >
              <option value="" disabled>
                Select airline
              </option>
              {airlines.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} · {a.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Fuel provider *
            <select
              className="form-select"
              name="provider_id"
              required
              defaultValue={value("provider_id")}
            >
              <option value="" disabled>
                Select provider
              </option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} · {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Billing month *
            <input
              className="form-control"
              type="month"
              name="billing_month"
              required
              defaultValue={value(
                "billing_month",
                new Date().toISOString().slice(0, 7),
              ).slice(0, 7)}
            />
          </label>
          <label>
            Fuel type *
            <input
              className="form-control"
              name="fuel_type"
              placeholder="JET A-1"
              required
              maxLength="40"
              defaultValue={value("fuel_type")}
            />
          </label>
          <label>
            Quantity ({quantityUnit}) *
            <input
              className="form-control"
              type="number"
              name="quantity"
              min="0.001"
              step="0.001"
              required
              defaultValue={value("quantity")}
            />
          </label>
          <label>
            Tax amount
            <input
              className="form-control"
              type="number"
              name="tax_amount"
              min="0"
              step="0.01"
              defaultValue={value("tax_amount", "0")}
            />
          </label>
          <label className="wide">
            Notes
            <textarea
              className="form-control"
              name="notes"
              rows="3"
              maxLength="2000"
              defaultValue={value("notes")}
            />
          </label>
          <div className="wide form-actions">
            <Link
              to={id ? `/invoices/${id}` : "/invoices"}
              className="btn btn-light"
            >
              Cancel
            </Link>
            <button
              className="btn btn-primary"
              disabled={
                busy ||
                (!initial && Boolean(id)) ||
                !airlines.length ||
                !providers.length
              }
            >
              {busy
                ? "Saving…"
                : id
                  ? "Save draft changes"
                  : "Create draft invoice"}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
export default InvoiceForm;
