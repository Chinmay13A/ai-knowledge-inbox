import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { QueryResponse } from '../api/types'
import { sourceElementId, splitCitations } from '../lib/citations'
import { SourceList } from './SourceList'

const HIGHLIGHT_MS = 1500

export function AnswerView({ result }: { result: QueryResponse }) {
  const cards = useRef(new Map<number, HTMLLIElement>())
  const [highlightedId, setHighlightedId] = useState<number | null>(null)

  const sourceIds = useMemo(() => new Set(result.sources.map((source) => source.id)), [result.sources])
  // Rendered as React text/elements only (never as HTML), so model output can't inject markup.
  const segments = useMemo(() => splitCitations(result.answer, sourceIds), [result.answer, sourceIds])

  const registerCard = useCallback((id: number, element: HTMLLIElement | null) => {
    if (element) cards.current.set(id, element)
    else cards.current.delete(id)
  }, [])

  const showSource = (id: number) => {
    cards.current.get(id)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHighlightedId(id)
  }

  useEffect(() => {
    if (highlightedId === null) return
    const timer = setTimeout(() => setHighlightedId(null), HIGHLIGHT_MS)
    return () => clearTimeout(timer)
  }, [highlightedId])

  return (
    <article className="space-y-4">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">Question</p>
        <p className="break-words text-sm text-gray-800">{result.question}</p>
      </div>

      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">Answer</p>
        <p className="whitespace-pre-line break-words leading-relaxed">
          {segments.map((segment, index) =>
            segment.type === 'text' ? (
              <span key={index}>{segment.text}</span>
            ) : (
              <button
                key={index}
                type="button"
                onClick={() => showSource(segment.id)}
                aria-describedby={sourceElementId(segment.id)}
                aria-label={`Show source ${segment.id}`}
                className="mx-0.5 rounded bg-blue-50 px-1 align-super font-mono text-xs font-semibold text-blue-800 hover:bg-blue-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                [{segment.id}]
              </button>
            ),
          )}
        </p>
        {result.truncated && (
          <p className="mt-2 text-xs text-amber-700">The answer was cut off at the length limit.</p>
        )}
        {result.model && <p className="mt-2 text-xs text-gray-500">Answered by {result.model}</p>}
      </div>

      {result.sources.length > 0 ? (
        <SourceList sources={result.sources} highlightedId={highlightedId} registerCard={registerCard} />
      ) : (
        <p className="rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-600">
          No relevant content in your inbox for this question. Try rephrasing it, or save a note or link about it first.
        </p>
      )}
    </article>
  )
}
