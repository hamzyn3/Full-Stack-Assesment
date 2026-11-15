import { describe, expect, it } from 'vitest'
import { decimate } from './geometry'

const line = (n: number): [number, number][] => Array.from({ length: n }, (_, i) => [i, i * 2])

describe('decimate', () => {
  it('returns short polylines untouched', () => {
    const points = line(5)
    expect(decimate(points, 10)).toBe(points)
    expect(decimate(points, 5)).toBe(points)
  })

  it('caps the number of points and keeps the first and last', () => {
    const points = line(6000)
    const thinned = decimate(points, 400)
    expect(thinned).toHaveLength(400)
    expect(thinned[0]).toEqual(points[0])
    expect(thinned.at(-1)).toEqual(points.at(-1))
  })

  it('keeps points in order and evenly spread', () => {
    const thinned = decimate(line(1001), 11)
    expect(thinned.map(([lat]) => lat)).toEqual([0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
  })

  it('can reduce to just the endpoints', () => {
    expect(decimate(line(50), 2)).toEqual([
      [0, 0],
      [49, 98],
    ])
  })

  it('rejects a cap that cannot hold both endpoints', () => {
    expect(() => decimate(line(10), 1)).toThrow()
  })
})
