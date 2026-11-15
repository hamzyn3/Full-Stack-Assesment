import { useCallback, useEffect, useState } from 'react'
import { ApiError, fetchHeatmap } from './api'
import { decimate } from './geometry'
import type { HeatmapResponse, RoutesResponse } from './types'

export type HeatmapState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: HeatmapResponse }

/** Points per route sent to the backend; the corridor grid is far coarser than this. */
const MAX_POINTS_PER_ROUTE = 400

type Settled = { status: 'error'; message: string } | { status: 'success'; data: HeatmapResponse }

/**
 * Loads the 0-48 hour heatmap for a set of routes, separately so the route results never wait for it.
 *
 * A settled result is remembered together with the routes and attempt it was fetched for. The state is derived
 * from that, so new routes (or a retry) read as "loading" immediately, without setting state inside the effect.
 */
export function useHeatmap(routes: RoutesResponse | null): { heatmap: HeatmapState; retry: () => void } {
  const [attempt, setAttempt] = useState(0)
  const [settled, setSettled] = useState<{ forRoutes: RoutesResponse; attempt: number; result: Settled } | null>(null)
  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  useEffect(() => {
    if (!routes) return
    const controller = new AbortController()
    fetchHeatmap(
      {
        routes: routes.routes.map((route) => decimate(route.geometry, MAX_POINTS_PER_ROUTE)),
        departure_time: routes.departure_time,
        load_weight_lb: routes.load_weight_lb,
      },
      controller.signal,
    )
      .then((data) => setSettled({ forRoutes: routes, attempt, result: { status: 'success', data } }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        const message = error instanceof ApiError ? error.message : 'The heatmap could not be loaded.'
        setSettled({ forRoutes: routes, attempt, result: { status: 'error', message } })
      })
    return () => controller.abort()
  }, [routes, attempt])

  let heatmap: HeatmapState
  if (!routes) heatmap = { status: 'idle' }
  else if (settled?.forRoutes !== routes || settled.attempt !== attempt) heatmap = { status: 'loading' }
  else heatmap = settled.result
  return { heatmap, retry }
}
