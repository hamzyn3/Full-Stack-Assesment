import type { HeatmapState } from '../useHeatmap'
import type { RoutesResponse } from '../types'

interface Props {
  heatmap: HeatmapState
  routes: RoutesResponse
  hour: number
  onRetry: () => void
  onHourChange: (hour: number) => void
  visible: boolean
  onVisibleChange: (visible: boolean) => void
}

function hourLabel(startIso: string, hour: number): string {
  const when = new Date(new Date(startIso).getTime() + hour * 3_600_000)
  return when.toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function HeatmapControl({ heatmap, routes, hour, onRetry, onHourChange, visible, onVisibleChange }: Props) {
  const tripHours = Math.ceil(Math.max(...routes.routes.map((r) => r.duration_seconds)) / 3600)

  return (
    <div className="heat-control">
      <label className="heat-toggle">
        <input type="checkbox" checked={visible} onChange={(e) => onVisibleChange(e.target.checked)} />
        Weather heatmap
      </label>

      {heatmap.status === 'loading' && (
        <p className="heat-status" role="status">
          <span className="spinner" aria-hidden="true" /> Loading the 48-hour forecast…
        </p>
      )}
      {heatmap.status === 'error' && (
        <div className="heat-status error" role="alert">
          <span>Heatmap unavailable: {heatmap.message}</span>
          <button type="button" className="link-button" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}

      {heatmap.status === 'success' && (
        <div className="heat-slider">
          <div className="heat-time">
            <strong>
              +{hour}h · {hourLabel(heatmap.data.start_time, hour)}
            </strong>
            <span>Trip runs +0h to +{tripHours}h</span>
          </div>
          <input
            type="range"
            min={0}
            max={heatmap.data.hours - 1}
            step={1}
            value={hour}
            disabled={!visible}
            aria-label="Forecast hour after departure"
            aria-valuetext={`${hour} hours after departure, ${hourLabel(heatmap.data.start_time, hour)}`}
            onChange={(e) => onHourChange(Number(e.target.value))}
          />
          <div className="heat-scale" aria-hidden="true">
            <span>+0h</span>
            <span>+24h</span>
            <span>+48h</span>
          </div>
        </div>
      )}
    </div>
  )
}
