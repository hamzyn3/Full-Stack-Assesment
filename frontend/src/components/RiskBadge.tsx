import { RISK_COLORS, RISK_LABELS } from '../risk'
import type { RiskKey } from '../types'

export function RiskBadge({ risk }: { risk: RiskKey }) {
  return (
    <span className="badge" style={{ background: RISK_COLORS[risk], color: risk === 'moderate' ? '#1a1d23' : '#fff' }}>
      {RISK_LABELS[risk]}
    </span>
  )
}
