import type { Place, RoutesRequest, RoutesResponse } from './types'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {}

/** Turns the backend's `{error}` or DRF's `{field: [messages]}` bodies into one readable message. */
function messageFromBody(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>
    if (typeof record.error === 'string') return record.error
    const fields = Object.entries(record)
      .map(([field, value]) => `${field.replaceAll('_', ' ')}: ${Array.isArray(value) ? value.join(' ') : String(value)}`)
      .join('; ')
    if (fields) return fields
  }
  return `The server responded with an error (${status}).`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, init)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Could not reach the server. Check your connection and try again.')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(messageFromBody(body, response.status))
  return body as T
}

export async function fetchHealth(): Promise<{ status: string }> {
  return request('/api/health/')
}

export async function fetchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const data = await request<{ results: Place[] }>(`/api/geocode/?q=${encodeURIComponent(query)}`, { signal })
  return data.results
}

export async function fetchRoutes(body: RoutesRequest, signal?: AbortSignal): Promise<RoutesResponse> {
  return request('/api/routes/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}
