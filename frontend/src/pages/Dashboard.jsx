import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import {
  Empty,
  ErrorBox,
  InvoiceTable,
  Loading,
  PageHeading,
} from "../components/UI";
import { currency } from "../utils";

export function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [months, setMonths] = useState(12);
  useEffect(() => {
    api
      .get("/dashboard", { params: { months } })
      .then(({ data: d }) => {
        setData(d);
        setError("");
      })
      .catch((e) => setError(errorMessage(e)));
  }, [months]);
  if (error)
    return (
      <>
        <PageHeading
          eyebrow="OVERVIEW"
          title="Operations dashboard"
          subtitle="Live fuel billing activity and business performance."
        />
        <ErrorBox error={error} />
      </>
    );
  if (!data)
    return (
      <>
        <PageHeading
          eyebrow="OVERVIEW"
          title="Operations dashboard"
          subtitle="Live fuel billing activity and business performance."
        />
        <Loading />
      </>
    );
  const metrics = [
    [
      "Active providers",
      data.active_providers,
      "bi-fuel-pump",
      "Operations network",
    ],
    [
      "Active airlines",
      data.active_airlines,
      "bi-airplane",
      "Customer accounts",
    ],
    ["Active fuel rates", data.active_rates, "bi-tags", "Current rate records"],
    ["All invoices", data.total_invoices, "bi-receipt", "Across all periods"],
  ];
  return (
    <>
      <PageHeading
        eyebrow="OVERVIEW / LIVE DATA"
        title="Operations dashboard"
        subtitle="A clear view of activity across your fuel network."
        action={
          <Link to="/invoices/new" className="btn btn-primary">
            <i className="bi bi-plus-lg me-2" />
            Create invoice
          </Link>
        }
      />
      <section className="metric-grid">
        {metrics.map(([label, value, icon, foot], i) => (
          <div className={`metric-card metric-tone-${i}`} key={label}>
            <div className={`metric-icon tone-${i}`}>
              <i className={`bi ${icon}`} />
            </div>
            <span className="metric-label">{label}</span>
            <strong>{value}</strong>
            <small>{foot}</small>
          </div>
        ))}
      </section>
      <section className="insight-grid">
        <div className="panel monthly-panel">
          <div className="panel-head">
            <div>
              <span className="eyebrow">BILLING PERFORMANCE</span>
              <h2>Monthly invoices</h2>
            </div>
            <div className="d-flex align-items-center gap-3">
              <label className="visually-hidden" htmlFor="dashboard-period">
                Monthly billing period
              </label>
              <select
                id="dashboard-period"
                className="form-select form-select-sm"
                aria-label="Monthly billing period"
                value={months}
                onChange={(event) => setMonths(Number(event.target.value))}
              >
                <option value={3}>Last 3 months</option>
                <option value={6}>Last 6 months</option>
                <option value={12}>Last 12 months</option>
                <option value={24}>Last 24 months</option>
                <option value={36}>Last 36 months</option>
              </select>
              <span className="live-tag">
                <i /> LIVE DATA
              </span>
            </div>
          </div>
          <div className="month-callout">
            <div>
              <span>
                CURRENT MONTH ·{" "}
                {new Date()
                  .toLocaleString(undefined, { month: "long", year: "numeric" })
                  .toUpperCase()}
              </span>
              <b>
                {data.current_month_count} <small>invoices</small>
              </b>
            </div>
            <div className="month-currency-list">
              {(data.current_month_amounts || []).map((x) => (
                <strong key={x.currency}>
                  {currency(x.total, x.currency)}
                </strong>
              ))}
            </div>
          </div>
          <div className="bar-chart">
            {[...data.monthly_totals]
              .reverse()
              .slice(-8)
              .map((x) => {
                const comparable = data.monthly_totals.filter(
                  (m) => m.currency === x.currency,
                );
                const max = Math.max(
                  ...comparable.map((m) => Number(m.total)),
                  1,
                );
                return (
                  <div
                    className="bar-col"
                    title={`${x.month}: ${currency(x.total, x.currency)}`}
                    key={x.month + x.currency}
                  >
                    <div className="bar-track">
                      <div
                        className="bar"
                        style={{
                          height: `${Math.max(4, (Number(x.total) / max) * 100)}%`,
                        }}
                      />
                    </div>
                    <span>
                      {new Date(`${x.month}T00:00:00`).toLocaleString(
                        undefined,
                        { month: "short" },
                      )}{" "}
                      · {x.currency}
                    </span>
                  </div>
                );
              })}
            {data.monthly_totals.length === 0 && (
              <Empty
                title="No invoice activity yet"
                detail="Monthly billing appears here when invoices are created."
              />
            )}
          </div>
          <div className="chart-legend">
            <span>
              <i /> Invoice value by month
            </span>
            <small>Excludes cancelled invoices · grouped by currency</small>
          </div>
        </div>
        <div className="panel breakdown-panel">
          <div className="panel-head">
            <div>
              <span className="eyebrow">NETWORK ACTIVITY</span>
              <h2>Billing by provider</h2>
            </div>
            <Link className="text-link" to="/invoices">
              View invoices <i className="bi bi-arrow-up-right" />
            </Link>
          </div>
          {data.provider_totals.length ? (
            data.provider_totals.slice(0, 5).map((p, i) => {
              const comparable = data.provider_totals.filter(
                (x) => x.currency === p.currency,
              );
              const max = Math.max(
                ...comparable.map((x) => Number(x.total)),
                1,
              );
              return (
                <div className="summary-row" key={p.name + p.currency}>
                  <div className="summary-rank">0{i + 1}</div>
                  <div className="summary-main">
                    <div>
                      <b>{p.name}</b>
                      <span>{p.currency}</span>
                    </div>
                    <div className="progress">
                      <div
                        style={{ width: `${(Number(p.total) / max) * 100}%` }}
                      />
                    </div>
                  </div>
                  <strong>{currency(p.total, p.currency)}</strong>
                </div>
              );
            })
          ) : (
            <Empty
              title="No provider billing"
              detail="Provider summaries appear when invoices are created."
            />
          )}
          <div className="mini-stat">
            <span>Airline accounts billed</span>
            <b>{data.airline_totals.length}</b>
          </div>
        </div>
      </section>
      <section className="panel table-panel dashboard-summary">
        <div className="panel-head">
          <div>
            <span className="eyebrow">NETWORK ACTIVITY</span>
            <h2>Billing by airline</h2>
          </div>
          <Link className="text-link" to="/invoices">
            Explore billing <i className="bi bi-arrow-up-right" />
          </Link>
        </div>
        <div className="airline-summary-grid">
          {data.airline_totals.length ? (
            data.airline_totals.slice(0, 8).map((x) => (
              <div className="airline-summary" key={x.name + x.currency}>
                <span>{x.name}</span>
                <b>{currency(x.total, x.currency)}</b>
              </div>
            ))
          ) : (
            <Empty
              title="No airline billing yet"
              detail="Airline summaries appear as invoices are recorded."
            />
          )}
        </div>
      </section>
      <section className="panel recent-panel">
        <div className="panel-head">
          <div>
            <span className="eyebrow">LATEST ACTIVITY</span>
            <h2>Recent invoices</h2>
          </div>
          <Link to="/invoices" className="btn btn-outline-secondary btn-sm">
            All invoices <i className="bi bi-arrow-right ms-1" />
          </Link>
        </div>
        <InvoiceTable rows={data.recent_invoices} compact />
      </section>
    </>
  );
}
export default Dashboard;
