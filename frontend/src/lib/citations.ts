export type Segment = { type: 'text'; text: string } | { type: 'cite'; id: number }

// "[1]" or "[1, 3]" (same pattern the backend uses to extract citations).
const CITATION_GROUP = /\[(\d+(?:\s*,\s*\d+)*)\]/g

/**
 * Splits an answer into text and citation segments so citations can be rendered as links.
 * Numbers that don't match a returned source stay as plain text, so a hallucinated
 * citation never becomes a broken link.
 */
export function splitCitations(answer: string, validIds: ReadonlySet<number>): Segment[] {
  const segments: Segment[] = []
  let cursor = 0

  for (const match of answer.matchAll(CITATION_GROUP)) {
    const ids = match[1].split(',').map((part) => Number(part.trim()))
    if (!ids.every((id) => validIds.has(id))) continue // leave the whole group as text

    const start = match.index ?? 0
    pushText(segments, answer.slice(cursor, start))
    for (const id of ids) segments.push({ type: 'cite', id })
    cursor = start + match[0].length
  }
  pushText(segments, answer.slice(cursor))
  return segments
}

function pushText(segments: Segment[], text: string): void {
  if (!text) return
  const last = segments[segments.length - 1]
  if (last?.type === 'text') last.text += text
  else segments.push({ type: 'text', text })
}

/** DOM id of a source card, so citation buttons can reference it (aria-describedby). */
export function sourceElementId(id: number): string {
  return `source-${id}`
}
