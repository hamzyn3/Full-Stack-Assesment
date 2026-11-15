import type { RiskKey } from './types'

export const RISK_ORDER: RiskKey[] = ['low', 'moderate', 'high', 'severe', 'no_travel']

export const RISK_LABELS: Record<RiskKey, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No Travel',
}

export const RISK_COLORS: Record<RiskKey, string> = {
  low: '#2e9e5b',
  moderate: '#e3b505',
  high: '#f08a00',
  severe: '#d63a3a',
  no_travel: '#5b1f8f',
}

/** One identity colour per route, chosen to be distinct from the risk colours. */
export const ROUTE_COLORS = ['#1d4ed8', '#0e7490', '#475569']

export function routeColor(routeId: string): string {
  const number = Number(routeId.split('-')[1])
  return ROUTE_COLORS[(Number.isFinite(number) ? number - 1 : 0) % ROUTE_COLORS.length]
}
