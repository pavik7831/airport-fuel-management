const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

async function request(path, options = {}) {
  const token = localStorage.getItem('afm_token')
  const response = await fetch(`${API_URL}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Request failed')
  }
  return response.status === 204 ? null : response.json()
}
export const api = {
  login: (data) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/auth/me'),
  dashboard: () => request('/dashboard'),
  list: (type, search = '') => request(`/${type}${search ? `?search=${encodeURIComponent(search)}` : ''}`),
  create: (type, data) => request(`/${type}`, { method: 'POST', body: JSON.stringify(data) }),
  update: (type, id, data) => request(`/${type}/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (type, id) => request(`/${type}/${id}`, { method: 'DELETE' }),
}
