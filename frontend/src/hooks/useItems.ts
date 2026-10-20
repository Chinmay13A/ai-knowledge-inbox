import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, deleteItem, errorMessage, getItems, isAbortError } from '../api/client'
import type { Item } from '../api/types'

export const PAGE_SIZE = 50
export const POLL_INTERVAL_MS = 2000
export const MAX_POLL_INTERVAL_MS = 30_000
const MAX_PAGE = 200 // backend limit for ?limit=

export interface ItemsState {
  items: Item[]
  total: number
  loading: boolean
  loadingMore: boolean
  error: string | null
  hasMore: boolean
  deletingIds: ReadonlySet<number>
  refresh: () => void
  loadMore: () => void
  addItem: (item: Item) => void
  removeItem: (id: number) => Promise<void>
}

/**
 * Owns the saved-items list: initial load, paging, optimistic inserts, and polling while any
 * item is still being indexed in the background (status "pending").
 */
export function useItems(): ItemsState {
  const [items, setItems] = useState<Item[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deletingIds, setDeletingIds] = useState<ReadonlySet<number>>(() => new Set())

  const inFlight = useRef<AbortController | null>(null)
  const itemsRef = useRef<Item[]>(items) // latest items for callbacks, without re-creating them
  useEffect(() => {
    itemsRef.current = items
  }, [items])

  const fetchItems = useCallback(async (offset: number, limit: number, append: boolean) => {
    inFlight.current?.abort() // only the latest request may update state
    const controller = new AbortController()
    inFlight.current = controller
    try {
      const page = await getItems({ limit, offset }, controller.signal)
      setItems((previous) => (append ? mergeById(previous, page.items) : page.items))
      setTotal(page.total)
      setError(null)
    } catch (caught) {
      if (isAbortError(caught)) return
      setError(errorMessage(caught))
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null
        setLoading(false)
        setLoadingMore(false)
      }
    }
  }, [])

  // Reloads everything currently shown, so statuses of already-loaded pages update too.
  const reload = useCallback(() => {
    const limit = Math.min(MAX_PAGE, Math.max(PAGE_SIZE, itemsRef.current.length))
    return fetchItems(0, limit, false)
  }, [fetchItems])

  const refresh = useCallback(() => {
    setLoading(true)
    void reload()
  }, [reload])

  const loadMore = useCallback(() => {
    setLoadingMore(true)
    void fetchItems(itemsRef.current.length, PAGE_SIZE, true)
  }, [fetchItems])

  const addItem = useCallback((item: Item) => {
    setItems((previous) => [item, ...previous.filter((existing) => existing.id !== item.id)])
    setTotal((previous) => previous + 1)
  }, [])

  const dropItem = useCallback((id: number) => {
    setItems((previous) => previous.filter((item) => item.id !== id))
    setTotal((previous) => Math.max(0, previous - 1))
  }, [])

  const removeItem = useCallback(
    async (id: number) => {
      setDeletingIds((previous) => new Set(previous).add(id))
      try {
        await deleteItem(id)
        dropItem(id)
      } catch (caught) {
        // Already gone (404) is the state the user asked for; anything else is a real error.
        if (caught instanceof ApiError && caught.status === 404) dropItem(id)
        else setError(errorMessage(caught))
      } finally {
        setDeletingIds((previous) => {
          const next = new Set(previous)
          next.delete(id)
          return next
        })
      }
    },
    [dropItem],
  )

  useEffect(() => {
    void reload()
    return () => inFlight.current?.abort()
  }, [reload])

  // Poll while something is still indexing; each response re-arms the timer, and polling stops by
  // itself once nothing is pending. If statuses stop changing (e.g. an item left pending by a server
  // restart), the interval backs off to MAX_POLL_INTERVAL_MS; any change resets it. Skips a tick if
  // another request is in flight.
  const hasPending = items.some((item) => item.status === 'pending')
  const statusKey = items.map((item) => `${item.id}:${item.status}`).join(',')
  const pollDelay = useRef(POLL_INTERVAL_MS)
  const lastStatusKey = useRef('')
  useEffect(() => {
    if (!hasPending) {
      pollDelay.current = POLL_INTERVAL_MS
      return
    }
    pollDelay.current =
      statusKey === lastStatusKey.current ? Math.min(pollDelay.current * 2, MAX_POLL_INTERVAL_MS) : POLL_INTERVAL_MS
    lastStatusKey.current = statusKey
    const timer = setTimeout(() => {
      if (!inFlight.current) void reload()
    }, pollDelay.current)
    return () => clearTimeout(timer)
  }, [hasPending, items, statusKey, reload])

  return {
    items,
    total,
    loading,
    loadingMore,
    error,
    hasMore: items.length < total,
    deletingIds,
    refresh,
    loadMore,
    addItem,
    removeItem,
  }
}

function mergeById(existing: Item[], incoming: Item[]): Item[] {
  const seen = new Set(existing.map((item) => item.id))
  return [...existing, ...incoming.filter((item) => !seen.has(item.id))]
}
