import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, fetchHeatmap, fetchPlaces, fetchRoutes } from './api'

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) })
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('fetchPlaces', () => {
  it('url-encodes the query and unwraps results', async () => {
    const place = { label: 'Dallas, TX', lat: 32.7, lon: -96.8 }
    const fn = mockFetch(200, { results: [place] })
    await expect(fetchPlaces('new york & co')).resolves.toEqual([place])
    expect(fn.mock.calls[0][0]).toContain('/api/geocode/?q=new%20york%20%26%20co')
  })
})

describe('POST requests', () => {
  it('fetchRoutes sends JSON and returns the body', async () => {
    const fn = mockFetch(200, { routes: [] })
    const payload = {
      origin: 'A',
      destination: 'B',
      departure_time: '2026-11-16T10:00:00Z',
      load_weight_lb: 42000,
      checkpoint_interval_miles: 25 as const,
    }
    await expect(fetchRoutes(payload)).resolves.toEqual({ routes: [] })
    const [url, init] = fn.mock.calls[0]
    expect(url).toContain('/api/routes/')
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual(payload)
  })

  it('fetchHeatmap posts to the heatmap endpoint', async () => {
    const fn = mockFetch(200, { cells: [] })
    await fetchHeatmap({ routes: [[[1, 2]]], departure_time: 'x', load_weight_lb: 1 })
    expect(fn.mock.calls[0][0]).toContain('/api/heatmap/')
  })
})

describe('error handling', () => {
  it('uses the backend {error} message', async () => {
    mockFetch(422, { error: 'No route found.' })
    await expect(fetchRoutes({} as never)).rejects.toThrow('No route found.')
  })

  it('flattens DRF field errors into one readable message', async () => {
    mockFetch(400, { load_weight_lb: ['Must be positive.'], departure_time: ['Required.', 'Invalid.'] })
    await expect(fetchRoutes({} as never)).rejects.toThrow('load weight lb: Must be positive.; departure time: Required. Invalid.')
  })

  it('falls back to a status message when the body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.reject(new Error('bad json')) }))
    await expect(fetchRoutes({} as never)).rejects.toThrow('The server responded with an error (500).')
  })

  it('reports an unreachable server as an ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = await fetchPlaces('x').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as Error).message).toMatch(/Could not reach the server/)
  })

  it('lets aborts through untouched so callers can ignore them', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')))
    const error = await fetchPlaces('x').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(DOMException)
    expect(error).not.toBeInstanceOf(ApiError)
  })
})
