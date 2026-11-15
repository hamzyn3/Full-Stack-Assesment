import { formatDateTime, formatDuration, formatMiles } from '../format'
import { routeColor } from '../risk'
import type { RouteResult, RoutesResponse } from '../types'
import { CheckpointTable } from './CheckpointTable'
import { RiskBadge } from './RiskBadge'
import { RiskBar } from './RiskBar'

interface Props {
  data: RoutesResponse
  selectedId: string
  onSelect: (routeId: string) => void
}

function RouteCard({ route, selected, onSelect }: { route: RouteResult; selected: boolean; onSelect: () => void }) {
  return (
    <button type="button" className={`route-card${selected ? ' selected' : ''}`} aria-pressed={selected} onClick={onSelect}>
      <span className="route-card-head">
        <span className="swatch" style={{ background: routeColor(route.id) }} aria-hidden="true" />
        <span className="route-name">{route.name}</span>
        {route.recommended && <span className="tag">Recommended</span>}
        <RiskBadge risk={route.max_risk} />
      </span>

      <span className="stats">
        <span>
          <span className="stat-label">Distance</span>
          <span className="stat-value">{formatMiles(route.distance_miles)}</span>
        </span>
        <span>
          <span className="stat-label">Drive time</span>
          <span className="stat-value">{formatDuration(route.duration_seconds)}</span>
        </span>
        <span>
          <span className="stat-label">Arrival</span>
          <span className="stat-value">{formatDateTime(route.arrival_time)}</span>
        </span>
        <span>
          <span className="stat-label">Avg risk</span>
          <span className="stat-value">{route.average_risk.toFixed(2)} / 4</span>
        </span>
      </span>

      <RiskBar milesByRisk={route.miles_by_risk} />

      {route.has_no_travel && (
        <span className="warning-inline">Conditions on this route are No Travel for this load.</span>
      )}
    </button>
  )
}

export function SummaryPanel({ data, selectedId, onSelect }: Props) {
  const { recommendation, routes } = data
  const best = routes.find((r) => r.id === recommendation.route_id)
  const selected = routes.find((r) => r.id === selectedId) ?? routes[0]

  return (
    <section className="summary" aria-label="Route results">
      <div className={`recommendation${recommendation.all_routes_blocked ? ' blocked' : ''}`}>
        {recommendation.all_routes_blocked ? (
          <>
            <strong>No safe route for this load and departure time.</strong>
            <p>{recommendation.reason}</p>
            <p>Consider a different departure time.</p>
          </>
        ) : (
          <>
            <strong>Recommended: {best?.name}</strong>
            <p>{recommendation.reason}</p>
          </>
        )}
      </div>

      <p className="trip-line">
        {data.origin.label} → {data.destination.label}
        <br />
        Departing {formatDateTime(data.departure_time)} · {data.load_weight_lb.toLocaleString()} lb · checkpoint every{' '}
        {data.checkpoint_interval_miles} mi
      </p>

      <div className="route-cards">
        {routes.map((route) => (
          <RouteCard
            key={route.id}
            route={route}
            selected={route.id === selected.id}
            onSelect={() => onSelect(route.id)}
          />
        ))}
      </div>

      <CheckpointTable route={selected} />
    </section>
  )
}
