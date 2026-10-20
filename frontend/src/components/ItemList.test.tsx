import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Item } from '../api/types'
import { makeItem } from '../test/fixtures'
import { ItemList } from './ItemList'

function renderList(items: Item[], overrides: Partial<Parameters<typeof ItemList>[0]> = {}) {
  const props = {
    items,
    total: items.length,
    loading: false,
    loadingMore: false,
    error: null,
    hasMore: false,
    refresh: vi.fn(),
    loadMore: vi.fn(),
    ...overrides,
  }
  render(<ItemList {...props} />)
  return props
}

describe('ItemList', () => {
  it('shows an empty state', () => {
    renderList([])

    expect(screen.getByText(/Nothing saved yet/)).toBeInTheDocument()
  })

  it('shows a status badge per item and the failure reason', () => {
    renderList([
      makeItem({ id: 1, title: 'Pending note', status: 'pending' }),
      makeItem({ id: 2, title: 'Ready note', status: 'ready' }),
      makeItem({ id: 3, title: 'Failed note', status: 'failed', error: 'Gemini rejected the API key' }),
    ])

    const rows = screen.getAllByRole('listitem')
    expect(within(rows[0]).getByText('Indexing…')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Ready')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Failed')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Gemini rejected the API key')).toBeInTheDocument()
  })

  it('links URL items safely to their source', () => {
    renderList([makeItem({ source_type: 'url', title: 'RAG - Wikipedia', url: 'https://en.wikipedia.org/wiki/RAG' })])

    const link = screen.getByRole('link', { name: 'RAG - Wikipedia' })
    expect(link).toHaveAttribute('href', 'https://en.wikipedia.org/wiki/RAG')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('offers retry on error and load more when there are more items', async () => {
    const user = userEvent.setup()
    const props = renderList([makeItem()], { error: 'Backend unreachable', hasMore: true, total: 60 })

    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await user.click(screen.getByRole('button', { name: /Load more \(59 left\)/ }))

    expect(props.refresh).toHaveBeenCalledTimes(1)
    expect(props.loadMore).toHaveBeenCalledTimes(1)
  })
})
