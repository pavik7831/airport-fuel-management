import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import {
  Empty,
  ErrorBox,
  InvoiceTable,
  Loading,
  PageHeading,
  Pager,
} from "../components/UI";

export function Invoices() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [airline, setAirline] = useState(""),
    [provider, setProvider] = useState(""),
    [month, setMonth] = useState(""),
    [airlines, setAirlines] = useState([]),
    [providers, setProviders] = useState([]),
    [page, setPage] = useState(1);
  useEffect(() => {
    Promise.all([
      api.get("/airlines", { params: { page_size: 100 } }),
      api.get("/providers", { params: { page_size: 100 } }),
    ])
      .then(([a, p]) => {
        setAirlines(a.data.items);
        setProviders(p.data.items);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);
  const load = useCallback(
    () =>
      api
        .get("/invoices", {
          params: {
            q,
            airline_id: airline || undefined,
            provider_id: provider || undefined,
            billing_month: month ? `${month}-01` : undefined,
            status: status || undefined,
            page,
            page_size: 10,
          },
        })
        .then((r) => {
          setData(r.data);
          setError("");
        })
        .catch((e) => setError(errorMessage(e))),
    [q, status, airline, provider, month, page],
  );
  useEffect(() => {
    load();
  }, [load]);
  async function exportCsv() {
    try {
      const r = await api.get("/invoices/export.csv", { responseType: "blob" });
      const url = URL.createObjectURL(r.data),
        a = document.createElement("a");
      a.href = url;
      a.download = "invoices.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  const resetPage = (fn) => (e) => {
    fn(e.target.value);
    setPage(1);
  };
  return (
    <>
      <PageHeading
        eyebrow="BILLING & COLLECTIONS"
        title="Invoices"
        subtitle="Review monthly fuel invoices and their lifecycle status."
        action={
          <div>
            <button
              onClick={exportCsv}
              className="btn btn-outline-secondary me-2"
            >
              <i className="bi bi-download me-2" />
              Export CSV
            </button>
            <Link to="/invoices/new" className="btn btn-primary">
              <i className="bi bi-plus-lg me-2" />
              Create invoice
            </Link>
          </div>
        }
      />
      <ErrorBox error={error} />
      <div className="panel table-panel">
        <div className="invoice-filters">
          <div className="search-box">
            <i className="bi bi-search" />
            <input
              value={q}
              onChange={resetPage(setQ)}
              placeholder="Search invoice reference…"
              aria-label="Search invoice reference"
            />
          </div>
          <select
            className="form-select"
            value={airline}
            onChange={resetPage(setAirline)}
            aria-label="Filter airline"
          >
            <option value="">All airlines</option>
            {airlines.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} · {a.name}
              </option>
            ))}
          </select>
          <select
            className="form-select"
            value={provider}
            onChange={resetPage(setProvider)}
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
            type="month"
            value={month}
            onChange={resetPage(setMonth)}
            aria-label="Filter billing month"
          />
          <select
            className="form-select"
            value={status}
            onChange={resetPage(setStatus)}
            aria-label="Filter status"
          >
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="FINALIZED">Finalized</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
        {data?.items.length ? (
          <InvoiceTable rows={data.items} />
        ) : data ? (
          <Empty
            title="No invoices found"
            detail="Create an invoice to start monthly billing."
          />
        ) : (
          <Loading />
        )}
        <Pager
          page={data?.page || page}
          pages={data?.pages || 0}
          onPage={setPage}
        />
      </div>
    </>
  );
}
export default Invoices;
