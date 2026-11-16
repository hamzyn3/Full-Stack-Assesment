// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { HeatmapState } from '../useHeatmap'
import type { RiskKey, RoutesResponse } from '../types'
import { HeatmapControl } from './HeatmapControl'
import { RiskBadge } from './RiskBadge'
import { RiskBar } from './RiskBar'

afterEach(cleanup)

const miles = (overrides: Partial<Record<RiskKey, number>>): Record<RiskKey, number> => ({
  low: 0,
  moderate: 0,
  high: 0,
  severe: 0,
  no_travel: 0,
  ...overrides,
})

describe('RiskBadge', () => {
  it('shows the human label', () => {
    render(<RiskBadge risk="no_travel" />)
    expect(screen.getByText('No Travel')).toBeTruthy()
  })
})

describe('RiskBar', () => {
  it('only lists levels that have miles and describes them for screen readers', () => {
    render(<RiskBar milesByRisk={miles({ low: 150, severe: 50 })} />)
    const bar = screen.getByRole('img')
    expect(bar.getAttribute('aria-label')).toBe('Miles by risk: Low 150 mi, Severe 50 mi')
    expect(screen.queryByText(/Moderate/)).toBeNull()
  })

  it('sizes segments by their share of the route', () => {
    render(<RiskBar milesByRisk={miles({ low: 75, high: 25 })} />)
    const widths = Array.from(screen.getByRole('img').children).map((el) => (el as HTMLElement).style.width)
    expect(widths).toEqual(['75%', '25%'])
  })
})

describe('HeatmapControl', () => {
  const routes = { routes: [{ duration_seconds: 3600 * 5 + 10 }, { duration_seconds: 3600 * 3 }] } as RoutesResponse
  const success: HeatmapState = {
    status: 'success',
    data: { start_time: '2026-11-16T10:00:00Z', hours: 49, cell_miles: 1, cells: [] },
  }

  function setup(heatmap: HeatmapState, visible = true) {
    const props = { onRetry: vi.fn(), onHourChange: vi.fn(), onVisibleChange: vi.fn() }
    render(<HeatmapControl heatmap={heatmap} routes={routes} hour={3} visible={visible} {...props} />)
    return props
  }

  it('shows a loading status while the forecast loads', () => {
    setup({ status: 'loading' })
    expect(screen.getByRole('status').textContent).toMatch(/Loading the 48-hour forecast/)
  })

  it('shows the error with a working retry button', () => {
    const { onRetry } = setup({ status: 'error', message: 'Rate limited.' })
    expect(screen.getByRole('alert').textContent).toMatch(/Rate limited\./)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('offers a 0-48 hour slider and reports hour changes', () => {
    const { onHourChange } = setup(success)
    const slider = screen.getByLabelText('Forecast hour after departure') as HTMLInputElement
    expect([slider.min, slider.max, slider.value]).toEqual(['0', '48', '3'])
    fireEvent.change(slider, { target: { value: '12' } })
    expect(onHourChange).toHaveBeenCalledWith(12)
  })

  it('rounds the trip length up to whole hours', () => {
    setup(success)
    expect(screen.getByText('Trip runs +0h to +6h')).toBeTruthy()
  })

  it('disables the slider when the heatmap is hidden and reports toggles', () => {
    const { onVisibleChange } = setup(success, false)
    expect((screen.getByLabelText('Forecast hour after departure') as HTMLInputElement).disabled).toBe(true)
    fireEvent.click(screen.getByLabelText('Weather heatmap'))
    expect(onVisibleChange).toHaveBeenCalledWith(true)
  })
})
