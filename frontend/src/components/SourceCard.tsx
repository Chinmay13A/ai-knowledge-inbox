import { useState, type Ref } from 'react'
import type { QuerySource } from '../api/types'
import { sourceElementId } from '../lib/citations'

interface SourceCardProps {
  source: QuerySource
  highlighted: boolean
  ref?: Ref<HTMLLIElement>
}

export function SourceCard({ source, highlighted, ref }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false)
  const isLong = source.snippet.length > 280

  return (
    <li
      ref={ref}
      id={sourceElementId(source.id)}
      data-highlighted={highlighted || undefined}
      className={`scroll-mt-4 rounded-md border p-3 transition-shadow ${
        source.cited ? 'border-gray-200 bg-white' : 'border-gray-100 bg-gray-50 opacity-80'
      } ${highlighted ? 'ring-2 ring-blue-400' : ''}`}
    >
      <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <span className="rounded bg-blue-50 px-1.5 font-mono text-xs font-semibold text-blue-800">[{source.id}]</span>
        {source.item_url ? (
          <a
            href={source.item_url}
            target="_blank"
            rel="noopener noreferrer"
            className="break-words font-medium text-blue-700 hover:underline"
          >
            {source.item_title}
          </a>
        ) : (
          <span className="break-words font-medium">{source.item_title}</span>
        )}
        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-gray-600">
          {source.source_type === 'url' ? 'URL' : 'Note'}
        </span>
        <span className="ml-auto text-xs text-gray-500" title="Cosine similarity between your question and this passage">
          {Math.round(source.score * 100)}% match
        </span>
      </div>

      <p className={`whitespace-pre-line break-words text-sm text-gray-700 ${expanded ? '' : 'line-clamp-4'}`}>
        {source.snippet}
      </p>
      {isLong && (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
          className="mt-1 text-xs font-medium text-blue-700 hover:underline"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </li>
  )
}
