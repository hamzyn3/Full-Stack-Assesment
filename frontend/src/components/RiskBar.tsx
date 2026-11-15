import { formatMiles } from '../format'
import { RISK_COLORS, RISK_LABELS, RISK_ORDER } from '../risk'
import type { RiskKey } from '../types'

interface Props {
  milesByRisk: Record<RiskKey, number>
}

/** Stacked bar showing how many miles of a route fall in each risk level. */
export function RiskBar({ milesByRisk }: Props) {
  const present = RISK_ORDER.filter((level) => milesByRisk[level] > 0)
  const total = present.reduce((sum, level) => sum + milesByRisk[level], 0)
  const description = present.map((level) => `${RISK_LABELS[level]} ${formatMiles(milesByRisk[level])}`).join(', ')

  return (
    <div className="risk-bar-wrap">
      <div className="risk-bar" role="img" aria-label={`Miles by risk: ${description}`}>
        {present.map((level) => (
          <span
            key={level}
            style={{ width: `${(milesByRisk[level] / total) * 100}%`, background: RISK_COLORS[level] }}
          />
        ))}
      </div>
      <ul className="risk-legend">
        {present.map((level) => (
          <li key={level}>
            <span className="dot" style={{ background: RISK_COLORS[level] }} aria-hidden="true" />
            {RISK_LABELS[level]} {formatMiles(milesByRisk[level])}
          </li>
        ))}
      </ul>
    </div>
  )
}
