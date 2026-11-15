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

/** Heatmap fill opacity per risk level (index = level). Calm weather stays faint so hazards stand out. */
export const HEAT_OPACITY = [0.25, 0.55, 0.7, 0.8, 0.85]

/** Risk level index (0-4) to its key; anything else (e.g. -1, no forecast) has no key. */
export function riskKeyFromLevel(level: number): RiskKey | null {
  return RISK_ORDER[level] ?? null
}
