const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** "just now", "5 min ago", "3 h ago", "2 days ago", then a plain date. */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const elapsed = now.getTime() - new Date(iso).getTime()
  if (elapsed < MINUTE) return 'just now'
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)} min ago`
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)} h ago`
  const days = Math.floor(elapsed / DAY)
  if (days < 7) return days === 1 ? '1 day ago' : `${days} days ago`
  return new Date(iso).toLocaleDateString()
}

export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString()
}
