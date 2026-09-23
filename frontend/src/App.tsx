import { FormEvent, useEffect, useState } from 'react'

import {
  createAirline,
  createFuelProvider,
  createFuelRate,
  DashboardSummary,
  FuelRate,
  FuelRateInput,
  generateInvoice,
  getAirlines,
  getDashboardSummary,
  getFuelProviders,
  getFuelRates,
  getInvoices,
  Invoice,
  Party,
  PartyInput,
  updateAirline,
  updateFuelProvider,
  updateFuelRate,
  login,
} from './api/client'

import './styles.css'

type Page =
  | 'dashboard'
  | 'fuel-rates'
  | 'fuel-providers'
  | 'airlines'
  | 'invoices'

const defaultRate: FuelRateInput = {
  fuel_type: 'Jet A-1',
  rate_per_litre: '',
  currency: 'INR',
  effective_from: new Date().toISOString().slice(0, 10),
}

const defaultParty: PartyInput = {
  code: '',
  name: '',
  contact_person: '',
  email: '',
  phone: '',
}

const defaultInvoice = {
  fuel_provider_id: '',
  airline_id: '',
  fuel_rate_id: '',
  billing_month: new Date().toISOString().slice(0, 7) + '-01',
  fuel_quantity_litres: '',
}

export default function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem('accessToken') ?? '',
  )

  const [email, setEmail] = useState('admin@airportfuel.com')
  const [password, setPassword] = useState('')
  const [page, setPage] = useState<Page>('dashboard')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [rates, setRates] = useState<FuelRate[]>([])
  const [providers, setProviders] = useState<Party[]>([])
  const [airlines, setAirlines] = useState<Party[]>([])
  const [invoices, setInvoices] = useState<Invoice[]>([])

  async function loadData() {
    const [
      dashboard,
      fuelRates,
      fuelProviders,
      airlineList,
      invoiceList,
    ] = await Promise.all([
      getDashboardSummary(token),
      getFuelRates(token),
      getFuelProviders(token),
      getAirlines(token),
      getInvoices(token),
    ])

    setSummary(dashboard)
    setRates(fuelRates)
    setProviders(fuelProviders)
    setAirlines(airlineList)
    setInvoices(invoiceList)
  }

  useEffect(() => {
    if (!token) return

    loadData().catch((error) => {
      setMessage(error instanceof Error ? error.message : 'Loading failed')
    })
  }, [token])

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setMessage('')

    try {
      const accessToken = await login(email, password)

      sessionStorage.setItem('accessToken', accessToken)
      setToken(accessToken)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  function logout() {
    sessionStorage.removeItem('accessToken')
    setToken('')
  }

  if (!token) {
    return (
      <main className="page">
        <form className="login-card" onSubmit={handleLogin}>
          <p className="eyebrow">Airport Fuel Management</p>
          <h1>Admin Login</h1>

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          <button disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>

          {message && <p className="message error">{message}</p>}
        </form>
      </main>
    )
  }

  return (
    <main className="app-layout">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">AFM</p>
          <h2 className="brand-title">Airport Fuel</h2>
        </div>

        <nav className="navigation">
          <button
            className={page === 'dashboard' ? 'nav-active' : 'nav-button'}
            onClick={() => setPage('dashboard')}
          >
            Dashboard
          </button>

          <button
            className={page === 'fuel-rates' ? 'nav-active' : 'nav-button'}
            onClick={() => setPage('fuel-rates')}
          >
            Fuel Rates
          </button>

          <button
            className={
              page === 'fuel-providers' ? 'nav-active' : 'nav-button'
            }
            onClick={() => setPage('fuel-providers')}
          >
            Fuel Providers
          </button>

          <button
            className={page === 'airlines' ? 'nav-active' : 'nav-button'}
            onClick={() => setPage('airlines')}
          >
            Airlines
          </button>

          <button
            className={page === 'invoices' ? 'nav-active' : 'nav-button'}
            onClick={() => setPage('invoices')}
          >
            Invoices
          </button>
        </nav>

        <button className="secondary logout-button" onClick={logout}>
          Logout
        </button>
      </aside>

      <section className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Airport Fuel Management</p>
            <h1>{getPageTitle(page)}</h1>
          </div>

          <button
            className="secondary"
            disabled={loading}
            onClick={async () => {
              setLoading(true)
              setMessage('')

              try {
                await loadData()
              } catch (error) {
                setMessage(
                  error instanceof Error ? error.message : 'Refresh failed',
                )
              } finally {
                setLoading(false)
              }
            }}
          >
            Refresh
          </button>
        </header>

        {message && <p className="message">{message}</p>}

        {page === 'dashboard' && summary && (
          <Dashboard
            summary={summary}
            invoices={invoices}
          />
        )}

        {page === 'fuel-rates' && (
          <FuelRates
            token={token}
            rates={rates}
            onSaved={loadData}
          />
        )}

        {page === 'fuel-providers' && (
          <PartyManagement
            title="Fuel Providers"
            items={providers}
            token={token}
            create={createFuelProvider}
            update={updateFuelProvider}
            onSaved={loadData}
          />
        )}

        {page === 'airlines' && (
          <PartyManagement
            title="Airlines"
            items={airlines}
            token={token}
            create={createAirline}
            update={updateAirline}
            onSaved={loadData}
          />
        )}

        {page === 'invoices' && (
          <Invoices
            token={token}
            invoices={invoices}
            providers={providers}
            airlines={airlines}
            rates={rates}
            onSaved={loadData}
          />
        )}
      </section>
    </main>
  )
}

function getPageTitle(page: Page): string {
  const titles: Record<Page, string> = {
    dashboard: 'Dashboard',
    'fuel-rates': 'Fuel Rates',
    'fuel-providers': 'Fuel Providers',
    airlines: 'Airlines',
    invoices: 'Invoices',
  }

  return titles[page]
}

function Dashboard({
  summary,
  invoices,
}: {
  summary: DashboardSummary
  invoices: Invoice[]
}) {
  return (
    <>
      <div className="dashboard-grid">
        <SummaryCard
          title="Fuel Providers"
          value={summary.fuel_providers}
        />

        <SummaryCard
          title="Airlines"
          value={summary.airlines}
        />

        <SummaryCard
          title="Fuel Rates"
          value={summary.fuel_rates}
        />

        <SummaryCard
          title="Invoices"
          value={summary.invoices}
        />

        <SummaryCard
          title="Total Invoice Amount"
          value={`₹ ${Number(summary.total_invoiced_amount).toFixed(2)}`}
        />
      </div>

      <section className="panel">
        <h2>Recent Invoices</h2>

        {invoices.length === 0 ? (
          <p>No invoices available.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Invoice Number</th>
                  <th>Billing Month</th>
                  <th>Quantity</th>
                  <th>Total</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {invoices.slice(0, 5).map((invoice) => (
                  <tr key={invoice.id}>
                    <td>{invoice.invoice_number}</td>
                    <td>{invoice.billing_month}</td>
                    <td>{invoice.fuel_quantity_litres} L</td>
                    <td>
                      {invoice.currency}{' '}
                      {Number(invoice.total_amount).toFixed(2)}
                    </td>
                    <td>{invoice.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}

function SummaryCard({
  title,
  value,
}: {
  title: string
  value: string | number
}) {
  return (
    <section className="summary-card">
      <span>{title}</span>
      <strong>{value}</strong>
    </section>
  )
}

function FuelRates({
  token,
  rates,
  onSaved,
}: {
  token: string
  rates: FuelRate[]
  onSaved: () => Promise<void>
}) {
  const [form, setForm] = useState<FuelRateInput>(defaultRate)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState('')

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    try {
      if (editingId === null) {
        await createFuelRate(token, form)
      } else {
        await updateFuelRate(token, editingId, form)
      }

      setForm(defaultRate)
      setEditingId(null)
      await onSaved()
      setMessage('Fuel rate saved successfully.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Save failed')
    }
  }

  return (
    <div className="content-grid">
      <form className="panel" onSubmit={save}>
        <h2>{editingId === null ? 'Add Fuel Rate' : 'Update Fuel Rate'}</h2>

        <label>
          Fuel Type
          <input
            value={form.fuel_type}
            onChange={(event) =>
              setForm({ ...form, fuel_type: event.target.value })
            }
            required
          />
        </label>

        <label>
          Rate Per Litre
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={form.rate_per_litre}
            onChange={(event) =>
              setForm({ ...form, rate_per_litre: event.target.value })
            }
            required
          />
        </label>

        <label>
          Currency
          <input
            maxLength={3}
            value={form.currency}
            onChange={(event) =>
              setForm({
                ...form,
                currency: event.target.value.toUpperCase(),
              })
            }
            required
          />
        </label>

        <label>
          Effective From
          <input
            type="date"
            value={form.effective_from}
            onChange={(event) =>
              setForm({ ...form, effective_from: event.target.value })
            }
            required
          />
        </label>

        <button>{editingId === null ? 'Save Rate' : 'Update Rate'}</button>

        {editingId !== null && (
          <button
            type="button"
            className="secondary cancel"
            onClick={() => {
              setEditingId(null)
              setForm(defaultRate)
            }}
          >
            Cancel
          </button>
        )}

        {message && <p className="message">{message}</p>}
      </form>

      <section className="panel">
        <h2>Fuel Rates List</h2>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Fuel Type</th>
                <th>Rate</th>
                <th>Effective Date</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {rates.map((rate) => (
                <tr key={rate.id}>
                  <td>{rate.fuel_type}</td>
                  <td>
                    {rate.currency} {rate.rate_per_litre}
                  </td>
                  <td>{rate.effective_from}</td>
                  <td>
                    <button
                      className="link-button"
                      onClick={() => {
                        setEditingId(rate.id)
                        setForm({
                          fuel_type: rate.fuel_type,
                          rate_per_litre: rate.rate_per_litre,
                          currency: rate.currency,
                          effective_from: rate.effective_from,
                        })
                      }}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function PartyManagement({
  title,
  items,
  token,
  create,
  update,
  onSaved,
}: {
  title: string
  items: Party[]
  token: string
  create: (token: string, data: PartyInput) => Promise<Party>
  update: (token: string, id: number, data: PartyInput) => Promise<Party>
  onSaved: () => Promise<void>
}) {
  const [form, setForm] = useState<PartyInput>(defaultParty)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState('')

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    try {
      if (editingId === null) {
        await create(token, form)
      } else {
        await update(token, editingId, form)
      }

      setForm(defaultParty)
      setEditingId(null)
      await onSaved()
      setMessage('Saved successfully.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Save failed')
    }
  }

  return (
    <div className="content-grid">
      <form className="panel" onSubmit={save}>
        <h2>{editingId === null ? `Add ${title}` : `Update ${title}`}</h2>

        <label>
          Code
          <input
            value={form.code}
            onChange={(event) =>
              setForm({
                ...form,
                code: event.target.value.toUpperCase(),
              })
            }
            required
          />
        </label>

        <label>
          Name
          <input
            value={form.name}
            onChange={(event) =>
              setForm({ ...form, name: event.target.value })
            }
            required
          />
        </label>

        <label>
          Contact Person
          <input
            value={form.contact_person ?? ''}
            onChange={(event) =>
              setForm({ ...form, contact_person: event.target.value })
            }
          />
        </label>

        <label>
          Email
          <input
            type="email"
            value={form.email ?? ''}
            onChange={(event) =>
              setForm({ ...form, email: event.target.value })
            }
          />
        </label>

        <label>
          Phone
          <input
            value={form.phone ?? ''}
            onChange={(event) =>
              setForm({ ...form, phone: event.target.value })
            }
          />
        </label>

        <button>{editingId === null ? 'Save' : 'Update'}</button>

        {editingId !== null && (
          <button
            type="button"
            className="secondary cancel"
            onClick={() => {
              setEditingId(null)
              setForm(defaultParty)
            }}
          >
            Cancel
          </button>
        )}

        {message && <p className="message">{message}</p>}
      </form>

      <section className="panel">
        <h2>{title} List</h2>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Contact</th>
                <th>Phone</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.code}</td>
                  <td>{item.name}</td>
                  <td>{item.contact_person || '-'}</td>
                  <td>{item.phone || '-'}</td>
                  <td>
                    <button
                      className="link-button"
                      onClick={() => {
                        setEditingId(item.id)
                        setForm({
                          code: item.code,
                          name: item.name,
                          contact_person: item.contact_person ?? '',
                          email: item.email ?? '',
                          phone: item.phone ?? '',
                        })
                      }}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function Invoices({
  token,
  invoices,
  providers,
  airlines,
  rates,
  onSaved,
}: {
  token: string
  invoices: Invoice[]
  providers: Party[]
  airlines: Party[]
  rates: FuelRate[]
  onSaved: () => Promise<void>
}) {
  const [form, setForm] = useState(defaultInvoice)
  const [message, setMessage] = useState('')

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    try {
      await generateInvoice(token, {
        fuel_provider_id: Number(form.fuel_provider_id),
        airline_id: Number(form.airline_id),
        fuel_rate_id: Number(form.fuel_rate_id),
        billing_month: form.billing_month,
        fuel_quantity_litres: form.fuel_quantity_litres,
      })

      setForm(defaultInvoice)
      await onSaved()
      setMessage('Invoice generated successfully.')
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : 'Invoice generation failed',
      )
    }
  }

  return (
    <>
      <form className="panel invoice-form" onSubmit={save}>
        <h2>Generate Invoice</h2>

        <label>
          Fuel Provider
          <select
            value={form.fuel_provider_id}
            onChange={(event) =>
              setForm({ ...form, fuel_provider_id: event.target.value })
            }
            required
          >
            <option value="">Select Provider</option>

            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.code} - {provider.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Airline
          <select
            value={form.airline_id}
            onChange={(event) =>
              setForm({ ...form, airline_id: event.target.value })
            }
            required
          >
            <option value="">Select Airline</option>

            {airlines.map((airline) => (
              <option key={airline.id} value={airline.id}>
                {airline.code} - {airline.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Fuel Rate
          <select
            value={form.fuel_rate_id}
            onChange={(event) =>
              setForm({ ...form, fuel_rate_id: event.target.value })
            }
            required
          >
            <option value="">Select Fuel Rate</option>

            {rates.map((rate) => (
              <option key={rate.id} value={rate.id}>
                {rate.fuel_type} - {rate.currency} {rate.rate_per_litre}
              </option>
            ))}
          </select>
        </label>

        <label>
          Billing Month
          <input
            type="date"
            value={form.billing_month}
            onChange={(event) =>
              setForm({ ...form, billing_month: event.target.value })
            }
            required
          />
        </label>

        <label>
          Fuel Quantity (Litres)
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={form.fuel_quantity_litres}
            onChange={(event) =>
              setForm({
                ...form,
                fuel_quantity_litres: event.target.value,
              })
            }
            required
          />
        </label>

        <button>Generate Invoice</button>

        {message && <p className="message">{message}</p>}
      </form>

      <section className="panel">
        <h2>Invoice List</h2>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Invoice Number</th>
                <th>Month</th>
                <th>Quantity</th>
                <th>Total</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              {invoices.map((invoice) => (
                <tr key={invoice.id}>
                  <td>{invoice.invoice_number}</td>
                  <td>{invoice.billing_month}</td>
                  <td>{invoice.fuel_quantity_litres} L</td>
                  <td>
                    {invoice.currency} {invoice.total_amount}
                  </td>
                  <td>{invoice.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}