import { formatDateTime } from '../format'
import type { RouteResult } from '../types'
import { RiskBadge } from './RiskBadge'

export function CheckpointTable({ route }: { route: RouteResult }) {
  return (
    <details className="checkpoints">
      <summary>
        {route.name} checkpoints ({route.checkpoints.length})
      </summary>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Mile</th>
              <th scope="col">ETA</th>
              <th scope="col">Wind</th>
              <th scope="col">Rain</th>
              <th scope="col">Risk</th>
            </tr>
          </thead>
          <tbody>
            {route.checkpoints.map((c) => (
              <tr key={c.index}>
                <td>{c.mile.toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
                <td>{formatDateTime(c.eta)}</td>
                <td>{c.wind_mph.toFixed(1)} mph</td>
                <td>{c.rain_in_hr.toFixed(2)} in/hr</td>
                <td>
                  <RiskBadge risk={c.risk} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
