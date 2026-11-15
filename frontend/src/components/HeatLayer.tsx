import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { HEAT_OPACITY, RISK_COLORS, riskKeyFromLevel } from '../risk'
import type { HeatmapResponse } from '../types'

const HEAT_PANE = 'heat'
const MILES_TO_METERS = 1609.344
/** Circles overlap their neighbours so that, once blurred, the grid reads as a continuous surface. */
const OVERLAP = 0.75

interface Props {
  heatmap: HeatmapResponse
  hour: number
  visible: boolean
}

/**
 * Weather heatmap: one circle per corridor grid cell, coloured by that cell's risk at ``hour``.
 *
 * Circles are created once per dataset and only restyled when the hour changes. That is imperative on
 * purpose: dragging the slider then costs a loop of setStyle calls and one canvas redraw, with no React
 * reconciliation of hundreds of elements. The pane is blurred with CSS to turn the circles into a heatmap.
 */
export function HeatLayer({ heatmap, hour, visible }: Props) {
  const map = useMap()
  const circlesRef = useRef<L.Circle[]>([])

  // Build the circles when the dataset changes.
  useEffect(() => {
    const pane = map.getPane(HEAT_PANE) ?? map.createPane(HEAT_PANE)
    pane.classList.add('heat-pane')
    pane.style.zIndex = '350' // above the tiles, below the route lines
    pane.style.pointerEvents = 'none'

    const radius = heatmap.cell_miles * MILES_TO_METERS * OVERLAP
    const circles = heatmap.cells.map((cell) =>
      L.circle([cell.lat, cell.lon], { pane: HEAT_PANE, radius, stroke: false, fillOpacity: 0, interactive: false }),
    )
    const group = L.layerGroup(circles).addTo(map)
    circlesRef.current = circles
    return () => {
      group.remove()
      circlesRef.current = []
    }
  }, [map, heatmap])

  // Show or hide the whole pane without touching the circles.
  useEffect(() => {
    const pane = map.getPane(HEAT_PANE)
    if (pane) pane.style.display = visible ? '' : 'none'
  }, [map, visible, heatmap])

  // Recolour for the selected hour. Skipped while hidden; re-applied when shown again.
  useEffect(() => {
    if (!visible) return
    const circles = circlesRef.current
    heatmap.cells.forEach((cell, i) => {
      const level = cell.risk[hour] ?? -1
      const key = riskKeyFromLevel(level)
      circles[i]?.setStyle(
        key ? { fillColor: RISK_COLORS[key], fillOpacity: HEAT_OPACITY[level] } : { fillOpacity: 0 },
      )
    })
  }, [heatmap, hour, visible])

  return null
}
