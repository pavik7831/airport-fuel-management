import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { Empty, ErrorBox, Loading, PageHeading, Pager } from "../components/UI";

const entityFields = (kind) => [
  {
    name: "code",
    label: kind === "airlines" ? "Airline code" : "Provider code",
    required: true,
  },
  { name: "name", label: "Name", required: true },
  { name: "contact_person", label: "Contact person" },
  { name: "email", label: "Email", type: "email" },
  { name: "phone", label: "Phone" },
  { name: "address", label: "Address", wide: true },
];

export function EntityPage({ type, title, singular }) {
  const [data, setData] = useState(null),
    [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [error, setError] = useState(""),
    [edit, setEdit] = useState(null),
    [busy, setBusy] = useState(false),
    [page, setPage] = useState(1);
  const load = useCallback(
    () =>
      api
        .get(`/${type}`, {
          params: {
            q,
            active: status === "" ? undefined : status === "true",
            page,
            page_size: 10,
          },
        })
        .then(({ data: d }) => {
          setData(d);
          setError("");
        })
        .catch((e) => setError(errorMessage(e))),
    [type, q, status, page],
  );
  useEffect(() => {
    load();
  }, [load]);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    const f = new FormData(e.currentTarget);
    const body = Object.fromEntries(f.entries());
    body.active = body.active === "true";
    try {
      if (edit?.id) await api.put(`/${type}/${edit.id}`, body);
      else await api.post(`/${type}`, body);
      setEdit(null);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  async function deactivate(item) {
    if (
      !window.confirm(
        `Deactivate ${item.name}? Historical invoices will be preserved.`,
      )
    )
      return;
    try {
      await api.delete(`/${type}/${item.id}`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="MASTER DATA"
        title={title}
        subtitle={`Manage active ${title.toLowerCase()} and preserve billing history.`}
        action={
          <button className="btn btn-primary" onClick={() => setEdit({})}>
            <i className="bi bi-plus-lg me-2" />
            Add {singular.toLowerCase()}
          </button>
        }
      />
      <ErrorBox error={error} />
      {edit && (
        <div className="panel form-panel">
          <div className="panel-head">
            <div>
              <span className="eyebrow">MASTER RECORD</span>
              <h2>
                {edit.id ? "Edit" : "New"} {singular}
              </h2>
            </div>
            <button
              className="btn-close"
              onClick={() => setEdit(null)}
              aria-label="Close"
            />
          </div>
          <form onSubmit={save} className="form-grid">
            {entityFields(type).map((f) => (
              <label className={f.wide ? "wide" : ""} key={f.name}>
                {f.label}
                {f.required && " *"}
                <input
                  className="form-control"
                  type={f.type || "text"}
                  name={f.name}
                  defaultValue={edit[f.name] || ""}
                  required={f.required}
                  maxLength={f.name === "code" ? 24 : 160}
                />
              </label>
            ))}
            <label>
              Status
              <select
                className="form-select"
                name="active"
                defaultValue={String(edit.active ?? true)}
              >
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </label>
            <div className="wide form-actions">
              <button
                type="button"
                className="btn btn-light"
                onClick={() => setEdit(null)}
              >
                Cancel
              </button>
              <button className="btn btn-primary" disabled={busy}>
                {busy ? "Saving…" : "Save " + singular}
              </button>
            </div>
          </form>
        </div>
      )}
      <div className="panel table-panel">
        <div className="table-toolbar">
          <div className="search-box">
            <i className="bi bi-search" />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder={`Search ${title.toLowerCase()}…`}
              aria-label="Search"
            />
          </div>
          <select
            className="form-select status-select"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            aria-label="Filter status"
          >
            <option value="">All statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>
        {!data ? (
          <Loading />
        ) : data.items.length === 0 ? (
          <Empty
            title={`No ${title.toLowerCase()} found`}
            detail="Add a record to get started."
          />
        ) : (
          <div className="table-responsive">
            <table className="table align-middle">
              <thead>
                <tr>
                  <th>CODE</th>
                  <th>NAME</th>
                  <th>CONTACT</th>
                  <th>EMAIL / PHONE</th>
                  <th>STATUS</th>
                  <th className="text-end">ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((x) => (
                  <tr key={x.id}>
                    <td>
                      <span className="code-chip">{x.code}</span>
                    </td>
                    <td>
                      <b>{x.name}</b>
                      <small className="cell-sub">
                        {x.contact_person || "—"}
                      </small>
                    </td>
                    <td>{x.contact_person || "—"}</td>
                    <td>
                      {x.email || "—"}
                      <small className="cell-sub">{x.phone || ""}</small>
                    </td>
                    <td>
                      <span
                        className={`state ${x.active ? "state-active" : "state-inactive"}`}
                      >
                        {x.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="text-end">
                      <button
                        className="btn btn-sm btn-light me-1"
                        onClick={() => setEdit(x)}
                        aria-label={`Edit ${x.name}`}
                      >
                        <i className="bi bi-pencil" />
                      </button>
                      {x.active && (
                        <button
                          className="btn btn-sm btn-light text-danger"
                          onClick={() => deactivate(x)}
                          aria-label={`Deactivate ${x.name}`}
                        >
                          <i className="bi bi-person-dash" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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

export default EntityPage;
