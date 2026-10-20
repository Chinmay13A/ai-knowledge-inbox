import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { HealthResponse } from '../api/types'
import { jsonResponse, mockFetch } from '../test/fixtures'
import { HealthBadge } from './HealthBadge'

const HEALTHY: HealthResponse = { status: 'ok', database: 'ok', embeddings: 'ready', llm: 'ready' }

describe('HealthBadge', () => {
  it('shows ok when everything is ready', async () => {
    mockFetch(() => jsonResponse(HEALTHY))
    render(<HealthBadge />)

    expect(await screen.findByText('backend ok')).toBeInTheDocument()
  })

  it('warns when the AI provider is not configured', async () => {
    mockFetch(() => jsonResponse({ ...HEALTHY, embeddings: 'not_configured', llm: 'not_configured' }))
    render(<HealthBadge />)

    const label = await screen.findByText('AI not configured')
    expect(label.parentElement).toHaveAttribute('title', expect.stringContaining('EMBEDDING_API_KEY'))
  })

  it('reports a database problem (503)', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    mockFetch(() => jsonResponse({ ...HEALTHY, status: 'degraded', database: 'error' }, 503))
    render(<HealthBadge />)

    expect(await screen.findByText('database unavailable')).toBeInTheDocument()
  })

  it('reports an unreachable backend', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    render(<HealthBadge />)

    expect(await screen.findByText('backend unreachable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'retry' })).toBeInTheDocument()
  })
})
