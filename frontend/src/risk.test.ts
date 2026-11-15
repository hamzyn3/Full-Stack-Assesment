import { describe, expect, it } from 'vitest'
import { HEAT_OPACITY, RISK_COLORS, RISK_ORDER, ROUTE_COLORS, riskKeyFromLevel, routeColor } from './risk'

describe('riskKeyFromLevel', () => {
  it('maps backend levels 0-4 to risk keys in severity order', () => {
    expect([0, 1, 2, 3, 4].map(riskKeyFromLevel)).toEqual(['low', 'moderate', 'high', 'severe', 'no_travel'])
  })

  it('returns null for "no forecast" (-1) and out-of-range levels', () => {
    expect(riskKeyFromLevel(-1)).toBeNull()
    expect(riskKeyFromLevel(5)).toBeNull()
  })
})

describe('risk styling tables', () => {
  it('has a colour and a heat opacity for every level', () => {
    expect(HEAT_OPACITY).toHaveLength(RISK_ORDER.length)
    for (const level of RISK_ORDER) expect(RISK_COLORS[level]).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('makes the heatmap more opaque as risk rises', () => {
    expect([...HEAT_OPACITY].sort((a, b) => a - b)).toEqual(HEAT_OPACITY)
  })

  it('never reuses a risk colour for a route line', () => {
    const riskColors = new Set(Object.values(RISK_COLORS))
    for (const color of ROUTE_COLORS) expect(riskColors.has(color)).toBe(false)
  })
})

describe('routeColor', () => {
  it('assigns a stable colour per route number', () => {
    expect(routeColor('route-1')).toBe(ROUTE_COLORS[0])
    expect(routeColor('route-2')).toBe(ROUTE_COLORS[1])
    expect(routeColor('route-3')).toBe(ROUTE_COLORS[2])
  })

  it('falls back to the first colour for unexpected ids', () => {
    expect(routeColor('custom')).toBe(ROUTE_COLORS[0])
  })
})
