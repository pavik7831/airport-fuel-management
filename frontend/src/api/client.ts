const API_URL =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

export type FuelRate = {
  id: number
  fuel_type: string
  rate_per_litre: string
  currency: string
  effective_from: string
}

export type FuelRateInput = Omit<FuelRate, 'id'>

export type Party = {
  id: number
  code: string
  name: string
  contact_person: string | null
  email: string | null
  phone: string | null
}

export type PartyInput = Omit<Party, 'id'>

export type Invoice = {
  id: number
  invoice_number: string
  fuel_provider_id: number
  airline_id: number
  fuel_rate_id: number
  billing_month: string
  fuel_quantity_litres: string
  rate_per_litre: string
  currency: string
  total_amount: string
  status: string
}

export type InvoiceInput = {
  fuel_provider_id: number
  airline_id: number
  fuel_rate_id: number
  billing_month: string
  fuel_quantity_litres: string
}

export type DashboardSummary = {
  fuel_providers: number
  airlines: number
  fuel_rates: number
  invoices: number
  total_invoiced_amount: string
}

function getErrorMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg ?? 'Invalid input')
      .join(', ')
  }

  return 'Something went wrong'
}

async function request<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(getErrorMessage(body.detail))
  }

  return response.json()
}

// Authentication

export async function login(
  email: string,
  password: string,
): Promise<string> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(getErrorMessage(body.detail))
  }

  const data = await response.json()
  return data.access_token
}

// Dashboard

export function getDashboardSummary(
  token: string,
): Promise<DashboardSummary> {
  return request('/dashboard', token)
}

// Fuel Rates

export function getFuelRates(token: string): Promise<FuelRate[]> {
  return request('/fuel-rates', token)
}

export function createFuelRate(
  token: string,
  data: FuelRateInput,
): Promise<FuelRate> {
  return request('/fuel-rates', token, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateFuelRate(
  token: string,
  id: number,
  data: FuelRateInput,
): Promise<FuelRate> {
  return request(`/fuel-rates/${id}`, token, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

// Fuel Providers

export function getFuelProviders(token: string): Promise<Party[]> {
  return request('/fuel-providers', token)
}

export function createFuelProvider(
  token: string,
  data: PartyInput,
): Promise<Party> {
  return request('/fuel-providers', token, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateFuelProvider(
  token: string,
  id: number,
  data: PartyInput,
): Promise<Party> {
  return request(`/fuel-providers/${id}`, token, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

// Airlines

export function getAirlines(token: string): Promise<Party[]> {
  return request('/airlines', token)
}

export function createAirline(
  token: string,
  data: PartyInput,
): Promise<Party> {
  return request('/airlines', token, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateAirline(
  token: string,
  id: number,
  data: PartyInput,
): Promise<Party> {
  return request(`/airlines/${id}`, token, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

// Invoices

export function getInvoices(token: string): Promise<Invoice[]> {
  return request('/invoices', token)
}

export function generateInvoice(
  token: string,
  data: InvoiceInput,
): Promise<Invoice> {
  return request('/invoices/generate', token, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}