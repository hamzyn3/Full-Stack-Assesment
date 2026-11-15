import L from 'leaflet'
import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Marker, Pane, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { formatDateTime, formatMiles } from '../format'
import { RISK_COLORS, RISK_LABELS, RISK_ORDER, routeColor } from '../risk'
import type { Checkpoint, RouteResult, RoutesResponse } from '../types'
import { RiskBadge } from './RiskBadge'

const US_CENTER: L.LatLngTuple = [39.5, -98.35]
const CHECKPOINT_PANE = 'checkpoints'

const originIcon = L.divIcon({ className: 'pin', html: 'A', iconSize: [28, 28], iconAnchor: [14, 14] })
const destinationIcon = L.divIcon({ className: 'pin', html: 'B', iconSize: [28, 28], iconAnchor: [14, 14] })

interface Props {
  data: RoutesResponse | null
  selectedId: string | null
  onSelect: (routeId: string) => void
}

interface ActiveCheckpoint {
  data: RoutesResponse
  route: RouteResult
  checkpoint: Checkpoint
}

function FitBounds({ data }: { data: RoutesResponse }) {
  const map = useMap()
  const bounds = useMemo(() => {
    let south = 90
    let north = -90
    let west = 180
    let east = -180
    for (const route of data.routes) {
      for (const [lat, lon] of route.geometry) {
        if (lat < south) south = lat
        if (lat > north) north = lat
        if (lon < west) west = lon
        if (lon > east) east = lon
      }
    }
    return L.latLngBounds([south, west], [north, east])
  }, [data])

  useEffect(() => {
    map.fitBounds(bounds, { padding: [40, 40] })
  }, [map, bounds])

  return null
}

interface RouteLayerProps {
  route: RouteResult
  selected: boolean
  onSelect: (routeId: string) => void
  onCheckpoint: (route: RouteResult, checkpoint: Checkpoint) => void
}

/** One route's line and checkpoints. Memoized so only a selection change redraws it. */
const RouteLayer = memo(function RouteLayer({ route, selected, onSelect, onCheckpoint }: RouteLayerProps) {
  const lineRef = useRef<L.Polyline>(null)
  const color = routeColor(route.id)

  useEffect(() => {
    if (selected) lineRef.current?.bringToFront()
  }, [selected])

  const lineStyle = useMemo(
    () => ({ color, weight: selected ? 6 : 4, opacity: selected ? 0.9 : 0.5 }),
    [color, selected],
  )
  const eventHandlers = useMemo(() => ({ click: () => onSelect(route.id) }), [onSelect, route.id])

  return (
    <>
      <Polyline ref={lineRef} positions={route.geometry} pathOptions={lineStyle} eventHandlers={eventHandlers} />
      {route.checkpoints.map((checkpoint) => (
        <CircleMarker
          key={checkpoint.index}
          center={[checkpoint.lat, checkpoint.lon]}
          pane={CHECKPOINT_PANE}
          radius={selected ? 6 : 3.5}
          pathOptions={{
            color: '#ffffff',
            weight: selected ? 1.5 : 1,
            fillColor: RISK_COLORS[checkpoint.risk],
            fillOpacity: selected ? 1 : 0.7,
          }}
          eventHandlers={{ click: () => onCheckpoint(route, checkpoint) }}
        />
      ))}
    </>
  )
})

function CheckpointPopupContent({ route, checkpoint }: { route: RouteResult; checkpoint: Checkpoint }) {
  return (
    <div className="popup">
      <strong>
        {route.name} · mile {checkpoint.mile.toLocaleString(undefined, { maximumFractionDigits: 1 })}
      </strong>
      <dl>
        <dt>ETA</dt>
        <dd>{formatDateTime(checkpoint.eta)}</dd>
        <dt>Wind</dt>
        <dd>{checkpoint.wind_mph.toFixed(1)} mph</dd>
        <dt>Rain</dt>
        <dd>{checkpoint.rain_in_hr.toFixed(2)} in/hr</dd>
        <dt>Covers</dt>
        <dd>{formatMiles(checkpoint.segment_miles)} of road</dd>
        <dt>Risk</dt>
        <dd>
          <RiskBadge risk={checkpoint.risk} />
        </dd>
      </dl>
    </div>
  )
}

function Legend() {
  return (
    <div className="legend" aria-label="Map legend">
      <strong>Checkpoint risk</strong>
      <ul>
        {RISK_ORDER.map((level) => (
          <li key={level}>
            <span className="dot" style={{ background: RISK_COLORS[level] }} aria-hidden="true" />
            {RISK_LABELS[level]}
          </li>
        ))}
      </ul>
      <small>Click a dot for weather and ETA. Click a line to select a route.</small>
    </div>
  )
}

export function RouteMap({ data, selectedId, onSelect }: Props) {
  const [active, setActive] = useState<ActiveCheckpoint | null>(null)

  const popup = data && active && active.data === data ? active : null

  return (
    <div className="map-wrap">
      <MapContainer center={US_CENTER} zoom={4} preferCanvas className="map" scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Pane name={CHECKPOINT_PANE} style={{ zIndex: 450 }} />

        {data && (
          <>
            <FitBounds data={data} />
            {data.routes.map((route) => (
              <RouteLayer
                key={route.id}
                route={route}
                selected={route.id === selectedId}
                onSelect={onSelect}
                onCheckpoint={(r, checkpoint) => setActive({ data, route: r, checkpoint })}
              />
            ))}
            <Marker position={[data.origin.lat, data.origin.lon]} icon={originIcon} interactive={false} />
            <Marker position={[data.destination.lat, data.destination.lon]} icon={destinationIcon} interactive={false} />
          </>
        )}

        {popup && (
          <Popup
            key={`${popup.route.id}-${popup.checkpoint.index}`}
            position={[popup.checkpoint.lat, popup.checkpoint.lon]}
            // Only clear if this popup is still the active one: switching checkpoints unmounts
            // the old popup, and its close event must not wipe out the new selection.
            eventHandlers={{ remove: () => setActive((current) => (current === popup ? null : current)) }}
          >
            <CheckpointPopupContent route={popup.route} checkpoint={popup.checkpoint} />
          </Popup>
        )}
      </MapContainer>
      {data && <Legend />}
    </div>
  )
}
