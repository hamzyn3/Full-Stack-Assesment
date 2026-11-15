import { describe, expect, it } from 'vitest'
import { formatDuration, formatMiles, nextFullHour, toLocalInputValue } from './format'

describe('formatDuration', () => {
  it('formats hours and zero-padded minutes', () => {
    expect(formatDuration(15 * 3600 + 2 * 60)).toBe('15h 02m')
    expect(formatDuration(3600)).toBe('1h 00m')
  })

  it('formats under an hour as minutes only', () => {
    expect(formatDuration(45 * 60)).toBe('45m')
    expect(formatDuration(0)).toBe('0m')
  })

  it('rounds to the nearest minute, carrying into the hour', () => {
    expect(formatDuration(59 * 60 + 40)).toBe('1h 00m')
    expect(formatDuration(89)).toBe('1m')
  })
})

describe('formatMiles', () => {
  it('shows at most one decimal and the unit', () => {
    expect(formatMiles(783.64)).toMatch(/^783[.,]6 mi$/)
    expect(formatMiles(12)).toBe('12 mi')
  })
})

describe('toLocalInputValue', () => {
  it('formats local time for a datetime-local input', () => {
    expect(toLocalInputValue(new Date(2026, 10, 5, 7, 4))).toBe('2026-11-05T07:04')
  })
})

describe('nextFullHour', () => {
  it('rounds up to the following hour', () => {
    const result = nextFullHour(new Date(2026, 10, 15, 18, 29, 45))
    expect([result.getHours(), result.getMinutes(), result.getSeconds()]).toEqual([19, 0, 0])
  })

  it('moves to the next day after 23:00', () => {
    const result = nextFullHour(new Date(2026, 10, 15, 23, 10))
    expect([result.getDate(), result.getHours()]).toEqual([16, 0])
  })

  it('does not mutate its input', () => {
    const now = new Date(2026, 10, 15, 18, 29)
    nextFullHour(now)
    expect(now.getHours()).toBe(18)
  })
})
