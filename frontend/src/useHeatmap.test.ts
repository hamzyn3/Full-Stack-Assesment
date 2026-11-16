// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from './api'
import type { HeatmapResponse, RoutesResponse } from './types'
import { useHeatmap } from './useHeatmap'

const heat: HeatmapResponse = { start_time: '2026-11-16T10:00:00Z', hours: 49, cell_miles: 1, cells: [] }
const makeRoutes = (): RoutesResponse =>
  ({
    departure_time: '2026-11-16T10:00:00Z',
    load_weight_lb: 42000,
    routes: [{ geometry: Array.from({ length: 1000 }, (_, i) => [i, i]) }],
  }) as unknown as RoutesResponse

afterEach(() => vi.restoreAllMocks())

describe('useHeatmap', () => {
  it('stays idle without routes and never calls the API', () => {
    const spy = vi.spyOn(api, 'fetchHeatmap')
    const { result } = renderHook(() => useHeatmap(null))
    expect(result.current.heatmap).toEqual({ status: 'idle' })
    expect(spy).not.toHaveBeenCalled()
  })

  it('loads, then succeeds, sending decimated geometry', async () => {
    const spy = vi.spyOn(api, 'fetchHeatmap').mockResolvedValue(heat)
    const routes = makeRoutes()
    const { result } = renderHook(() => useHeatmap(routes))
    expect(result.current.heatmap.status).toBe('loading')
    await waitFor(() => expect(result.current.heatmap).toEqual({ status: 'success', data: heat }))
    const sent = spy.mock.calls[0][0]
    expect(sent.routes[0]).toHaveLength(400)
    expect(sent.load_weight_lb).toBe(42000)
  })

  it('reports an ApiError message and recovers on retry', async () => {
    const spy = vi
      .spyOn(api, 'fetchHeatmap')
      .mockRejectedValueOnce(new api.ApiError('Rate limited.'))
      .mockResolvedValueOnce(heat)
    const routes = makeRoutes()
    const { result } = renderHook(() => useHeatmap(routes))
    await waitFor(() => expect(result.current.heatmap).toEqual({ status: 'error', message: 'Rate limited.' }))

    act(() => result.current.retry())
    expect(result.current.heatmap.status).toBe('loading')
    await waitFor(() => expect(result.current.heatmap.status).toBe('success'))
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('uses a generic message for unexpected errors', async () => {
    vi.spyOn(api, 'fetchHeatmap').mockRejectedValue(new Error('boom'))
    const routes = makeRoutes()
    const { result } = renderHook(() => useHeatmap(routes))
    await waitFor(() =>
      expect(result.current.heatmap).toEqual({ status: 'error', message: 'The heatmap could not be loaded.' }),
    )
  })

  it('goes back to loading when new routes arrive', async () => {
    vi.spyOn(api, 'fetchHeatmap').mockResolvedValue(heat)
    const first = makeRoutes()
    const { result, rerender } = renderHook(({ routes }) => useHeatmap(routes), { initialProps: { routes: first } })
    await waitFor(() => expect(result.current.heatmap.status).toBe('success'))
    rerender({ routes: makeRoutes() })
    expect(result.current.heatmap.status).toBe('loading')
  })
})
