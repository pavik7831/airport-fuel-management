import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { Empty, ErrorBox, Loading, PageHeading } from "../components/UI";
import { currency } from "../utils";

export function Rates() {
  const [data, setData] = useState(null),
    [defaultCurrency, setDefaultCurrency] = useState("USD"),
    [providers, setProviders] = useState([]),
    [error, setError] = useState(""),
    [edit, setEdit] = useState(null),
    [providerFilter, setProviderFilter] = useState(""),
    [fuelFilter, setFuelFilter] = useState(""),
    [effectiveOn, setEffectiveOn] = useState("");
  const load = useCallback(
    () =>
      api
        .get("/rates", {
          params: {
            page_size: 100,
            provider_id: providerFilter || undefined,
            fuel_type: fuelFilter || undefined,
            effective_on: effectiveOn || undefined,
          },
        })
        .then((r) => setData(r.data))
        .catch((e) => setError(errorMessage(e))),
    [providerFilter, fuelFilter, effectiveOn],
  );
  useEffect(() => {
    load();
    api
      .get("/config")
      .then((r) => setDefaultCurrency(r.data.default_currency))
      .catch((e) => setError(errorMessage(e)));
    api
      .get("/providers", { params: { page_size: 100 } })
      .then((r) => setProviders(r.data.items))
      .catch((e) => setError(errorMessage(e)));
  }, [load]);
  async function submit(e) {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.currentTarget));
    d.provider_id = Number(d.provider_id);
    d.rate_per_unit = Number(d.rate_per_unit);
    d.active = edit.id ? d.active === "true" : true;
    try {
      if (edit.id) await api.put(`/rates/${edit.id}`, d);
      else await api.post("/rates", d);
      setEdit(null);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  async function deactivate(rate) {
    if (
      !window.confirm(
        "Deactivate this fuel rate? Historical invoices will keep their rate snapshot.",
      )
    )
      return;
    try {
      await api.delete(`/rates/${rate.id}`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  const value = (key, fallback = "") => edit?.[key] ?? fallback;
  return (
    <>
      <PageHeading
        eyebrow="RATE MANAGEMENT"
        title="Fuel rates"
        subtitle="Time-bound rates are selected by provider, fuel type and invoice date."
        action={
          <button onClick={() => setEdit({})} className="btn btn-primary">
            <i className="bi bi-plus-lg me-2" />
            Add rate
          </button>
        }
      />
      <ErrorBox error={error} />
      {edit && (
        <div className="panel form-panel">
          <div className="panel-head">
            <div>
              <span className="eyebrow">RATE HISTORY</span>
              <h2>{edit.id ? "Edit rate period" : "New rate period"}</h2>
            </div>
            <button
              className="btn-close"
              onClick={() => setEdit(null)}
              aria-label="Close"
            />
          </div>
          <form onSubmit={submit} className="form-grid">
            <label>
              Provider
              <select
                className="form-select"
                name="provider_id"
                required
                defaultValue={value(
                  "provider_id",
                  providers.find((p) => p.active)?.id || "",
                )}
              >
                {providers
                  .filter((p) => p.active || p.id === edit.provider_id)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.code} · {p.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Fuel type
              <input
                className="form-control"
                name="fuel_type"
                placeholder="JET A-1"
                required
                defaultValue={value("fuel_type")}
              />
            </label>
            <label>
              Rate / unit
              <input
                className="form-control"
                type="number"
                step="0.00001"
                min="0.00001"
                name="rate_per_unit"
                required
                defaultValue={value("rate_per_unit")}
              />
            </label>
            <label>
              Currency
              <input
                className="form-control"
                name="currency"
                defaultValue={value("currency", defaultCurrency)}
                pattern="[A-Z]{3}"
                maxLength="3"
                required
              />
            </label>
            <label>
              Effective from
              <input
                className="form-control"
                type="date"
                name="effective_from"
                required
                defaultValue={value("effective_from")}
              />
            </label>
            <label>
              Effective to
              <input
                className="form-control"
                type="date"
                name="effective_to"
                defaultValue={value("effective_to")}
              />
            </label>
            {edit.id && (
              <label>
                Status
                <select
                  className="form-select"
                  name="active"
                  defaultValue={String(edit.active)}
                >
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            )}
            <div className="wide form-actions">
              <button
                type="button"
                className="btn btn-light"
                onClick={() => setEdit(null)}
              >
                Cancel
              </button>
              <button className="btn btn-primary">Save rate</button>
            </div>
          </form>
        </div>
      )}
      <div className="panel table-panel">
        <div className="rate-filters">
          <select
            className="form-select"
            value={providerFilter}
            onChange={(e) => setProviderFilter(e.target.value)}
            aria-label="Filter provider"
          >
            <option value="">All providers</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} · {p.name}
              </option>
            ))}
          </select>
          <input
            className="form-control"
            value={fuelFilter}
            onChange={(e) => setFuelFilter(e.target.value)}
            placeholder="Fuel type"
            aria-label="Filter fuel type"
          />
          <input
            className="form-control"
            type="date"
            value={effectiveOn}
            onChange={(e) => setEffectiveOn(e.target.value)}
            aria-label="Applicable on date"
          />
        </div>
        <div className="table-responsive">
          <table className="table align-middle">
            <thead>
              <tr>
                <th>PROVIDER</th>
                <th>FUEL TYPE</th>
                <th>RATE / UNIT</th>
                <th>EFFECTIVE PERIOD</th>
                <th>STATUS</th>
                <th className="text-end">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((r) => (
                <tr key={r.id}>
                  <td>
                    {providers.find((p) => p.id === r.provider_id)?.name ||
                      `Provider #${r.provider_id}`}
                  </td>
                  <td>
                    <span className="code-chip">{r.fuel_type}</span>
                  </td>
                  <td>
                    <b>{currency(r.rate_per_unit, r.currency)}</b>
                  </td>
                  <td>
                    {r.effective_from} — {r.effective_to || "Open ended"}
                  </td>
                  <td>
                    <span
                      className={`state ${r.active ? "state-active" : "state-inactive"}`}
                    >
                      {r.active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="text-end">
                    <button
                      className="btn btn-sm btn-light me-1"
                      onClick={() => setEdit(r)}
                      aria-label={`Edit ${r.fuel_type} rate`}
                    >
                      <i className="bi bi-pencil" />
                    </button>
                    {r.active && (
                      <button
                        className="btn btn-sm btn-light text-danger"
                        onClick={() => deactivate(r)}
                        aria-label={`Deactivate ${r.fuel_type} rate`}
                      >
                        <i className="bi bi-tags" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data?.items.length === 0 && (
          <Empty
            title="No rates configured"
            detail="Add an effective dated fuel rate to enable invoicing."
          />
        )}
        {!data && <Loading />}
      </div>
    </>
  );
}
export default Rates;
