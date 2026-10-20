import type { ItemsState } from '../hooks/useItems'
import { ErrorBanner } from './ErrorBanner'
import { ItemRow } from './ItemRow'

type ItemListProps = Pick<
  ItemsState,
  'items' | 'total' | 'loading' | 'loadingMore' | 'error' | 'hasMore' | 'refresh' | 'loadMore'
>

export function ItemList({ items, total, loading, loadingMore, error, hasMore, refresh, loadMore }: ItemListProps) {
  return (
    <section aria-labelledby="saved-items-heading" className="rounded-lg border border-gray-200 bg-white">
      <h2 id="saved-items-heading" className="border-b border-gray-200 px-4 py-3 font-medium">
        Saved items {!loading && !error && <span className="text-gray-500">({total})</span>}
      </h2>

      {error && (
        <div className="p-4">
          <ErrorBanner message={error} onRetry={refresh} />
        </div>
      )}

      {loading && items.length === 0 ? (
        <ul aria-label="Loading saved items" className="space-y-3 p-4">
          {[0, 1, 2].map((key) => (
            <li key={key} className="h-14 animate-pulse rounded bg-gray-100" />
          ))}
        </ul>
      ) : items.length === 0 && !error ? (
        <p className="px-4 py-8 text-center text-sm text-gray-500">
          Nothing saved yet. Add a note or a link to start building your inbox.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {items.map((item) => (
            <ItemRow key={item.id} item={item} />
          ))}
        </ul>
      )}

      {hasMore && (
        <div className="border-t border-gray-100 p-3 text-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            {loadingMore ? 'Loading…' : `Load more (${total - items.length} left)`}
          </button>
        </div>
      )}
    </section>
  )
}
