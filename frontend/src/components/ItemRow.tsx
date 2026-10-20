import type { Item } from '../api/types'
import { formatRelativeTime, formatTimestamp } from '../lib/format'
import { StatusBadge } from './StatusBadge'

export function ItemRow({ item }: { item: Item }) {
  return (
    <li className="space-y-1.5 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="mr-2 rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-gray-600">
            {item.source_type === 'url' ? 'URL' : 'Note'}
          </span>
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="break-words font-medium text-blue-700 hover:underline"
            >
              {item.title}
            </a>
          ) : (
            <span className="break-words font-medium">{item.title}</span>
          )}
        </div>
        <StatusBadge status={item.status} />
      </div>

      <p className="line-clamp-3 whitespace-pre-line break-words text-sm text-gray-600">{item.preview}</p>

      {item.status === 'failed' && item.error && <p className="text-xs text-red-700">{item.error}</p>}

      <p className="text-xs text-gray-500">
        <time dateTime={item.created_at} title={formatTimestamp(item.created_at)}>
          {formatRelativeTime(item.created_at)}
        </time>
        {' · '}
        {item.chunk_count} {item.chunk_count === 1 ? 'chunk' : 'chunks'}
      </p>
    </li>
  )
}
