/** Thin a polyline to at most ``maxPoints`` points, always keeping the first and last. */
export function decimate<T>(points: T[], maxPoints: number): T[] {
  if (maxPoints < 2) throw new Error('maxPoints must be at least 2')
  if (points.length <= maxPoints) return points
  const result: T[] = []
  const step = (points.length - 1) / (maxPoints - 1)
  for (let i = 0; i < maxPoints; i++) {
    result.push(points[Math.round(i * step)])
  }
  return result
}
