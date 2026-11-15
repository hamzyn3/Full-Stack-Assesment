import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, fetchRoutes } from './api'
import { RouteForm } from './components/RouteForm'
import { RouteMap } from './components/RouteMap'
import { SummaryPanel } from './components/SummaryPanel'
import type { RoutesRequest, RoutesResponse } from './types'

type State =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: RoutesResponse }

export default function App() {
  const [state, setState] = useState<State>({ status: 'idle' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => () => controllerRef.current?.abort(), [])

  async function handleSubmit(request: RoutesRequest) {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller

    setState({ status: 'loading' })
    try {
      const data = await fetchRoutes(request, controller.signal)
      setSelectedId(data.recommendation.route_id)
      setState({ status: 'success', data })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      const message = error instanceof ApiError ? error.message : 'Something went wrong. Please try again.'
      setState({ status: 'error', message })
    }
  }

  const handleSelect = useCallback((routeId: string) => setSelectedId(routeId), [])

  const data = state.status === 'success' ? state.data : null

  return (
    <div className="layout">
      <aside className="sidebar">
        <header>
          <h1>Weather-Aware Truck Routing</h1>
          <p className="subtitle">Pick the safest route for your load, based on the weather you will actually drive through.</p>
        </header>

        <RouteForm loading={state.status === 'loading'} onSubmit={handleSubmit} />

        {state.status === 'loading' && (
          <p className="status" role="status">
            <span className="spinner" aria-hidden="true" /> Finding routes and checking the weather along each one…
          </p>
        )}
        {state.status === 'error' && (
          <p className="status error" role="alert">
            {state.message}
          </p>
        )}
        {data && selectedId && <SummaryPanel data={data} selectedId={selectedId} onSelect={handleSelect} />}
      </aside>

      <main className="map-area">
        <RouteMap data={data} selectedId={selectedId} onSelect={handleSelect} />
      </main>
    </div>
  )
}
