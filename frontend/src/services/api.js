// Shared API client — Spotter AI frontend (Phase 23+).
//
// - Base URL via VITE_API_BASE_URL (defaults to localhost:8000)
// - API key header injection for mutating endpoints (Phase 22)
// - Consistent error handling matching the backend envelope
//   {success: false, data: null, error: {code, message}}
// - Simple loading/error state helpers used by every screen

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const API_KEY = import.meta.env.VITE_API_KEY || 'spotter-demo'

export async function apiGet(path) {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  })
  return handleResponse(resp)
}

export async function apiPost(path, body) {
  const resp = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify(body),
  })
  return handleResponse(resp)
}

async function handleResponse(resp) {
  let payload = null
  try {
    payload = await resp.json()
  } catch {
    // Non-JSON body.
  }

  if (!resp.ok) {
    const message =
      payload?.error?.message || payload?.detail || `HTTP ${resp.status}`
    const error = new Error(message)
    error.status = resp.status
    error.payload = payload
    throw error
  }
  return payload
}

export const apiBaseUrl = BASE_URL
