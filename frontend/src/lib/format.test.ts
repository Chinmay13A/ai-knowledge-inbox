import { describe, expect, it } from 'vitest'
import { formatRelativeTime } from './format'

const NOW = new Date('2026-10-20T12:00:00Z')

function ago(ms: number): string {
  return new Date(NOW.getTime() - ms).toISOString()
}

describe('formatRelativeTime', () => {
  it.each([
    [10_000, 'just now'],
    [5 * 60_000, '5 min ago'],
    [3 * 3_600_000, '3 h ago'],
    [86_400_000, '1 day ago'],
    [4 * 86_400_000, '4 days ago'],
  ])('%i ms ago → %s', (elapsed, expected) => {
    expect(formatRelativeTime(ago(elapsed), NOW)).toBe(expected)
  })

  it('falls back to a date after a week', () => {
    expect(formatRelativeTime(ago(30 * 86_400_000), NOW)).toBe(new Date(ago(30 * 86_400_000)).toLocaleDateString())
  })
})
