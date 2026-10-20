import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { QueryResponse, QuerySource } from '../api/types'
import { jsonResponse, mockFetch } from '../test/fixtures'
import { AskPanel } from './AskPanel'

function source(id: number, overrides: Partial<QuerySource> = {}): QuerySource {
  return {
    id,
    cited: true,
    item_id: id,
    item_title: `Source ${id}`,
    item_url: null,
    source_type: 'note',
    chunk_index: 0,
    snippet: `Snippet ${id}`,
    score: 0.8,
    ...overrides,
  }
}

const RESPONSE: QueryResponse = {
  question: 'What is RAG?',
  answer: 'RAG retrieves documents [1] and cites them [9].',
  sources: [
    source(1, { item_title: 'RAG - Wikipedia', item_url: 'https://en.wikipedia.org/wiki/RAG', source_type: 'url', score: 0.81 }),
    source(2, { cited: false, snippet: 'x'.repeat(400) }),
  ],
  model: 'gemini:gemini-2.5-flash',
  truncated: false,
}

function setup(readyCount = 3) {
  render(<AskPanel readyCount={readyCount} />)
  return userEvent.setup()
}

async function askQuestion(user: ReturnType<typeof userEvent.setup>, question = 'What is RAG?') {
  await user.type(screen.getByLabelText('Question'), question)
  await user.keyboard('{Enter}')
}

describe('AskPanel', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('rejects a blank question without calling the API', async () => {
    const fetchMock = mockFetch(() => jsonResponse(RESPONSE))
    const user = setup()

    await user.click(screen.getByRole('button', { name: 'Ask' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Type a question first.')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('asks on Enter, but Shift+Enter only adds a new line', async () => {
    const fetchMock = mockFetch(() => jsonResponse(RESPONSE))
    const user = setup()

    await user.type(screen.getByLabelText('Question'), 'What is{Shift>}{Enter}{/Shift}RAG?')
    expect(fetchMock).not.toHaveBeenCalled()
    await user.keyboard('{Enter}')

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(String(init.body))).toEqual({ question: 'What is\nRAG?' })
  })

  it('renders the answer with clickable citations that jump to their source', async () => {
    mockFetch(() => jsonResponse(RESPONSE))
    const user = setup()
    await askQuestion(user)

    const citation = await screen.findByRole('button', { name: 'Show source 1' })
    expect(screen.queryByRole('button', { name: 'Show source 9' })).not.toBeInTheDocument()
    expect(screen.getByText(/and cites them \[9\]/)).toBeInTheDocument() // invalid number stays text

    await user.click(citation)

    const card = document.getElementById('source-1') as HTMLElement
    expect(card.scrollIntoView).toHaveBeenCalled()
    expect(card).toHaveAttribute('data-highlighted', 'true')
    expect(screen.getByText('Answered by gemini:gemini-2.5-flash')).toBeInTheDocument()
  })

  it('groups uncited sources and shows source details', async () => {
    mockFetch(() => jsonResponse(RESPONSE))
    const user = setup()
    await askQuestion(user)

    const link = await screen.findByRole('link', { name: 'RAG - Wikipedia' })
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByText('81% match')).toBeInTheDocument()

    const others = screen.getByText('Also retrieved (not cited)').parentElement as HTMLElement
    expect(within(others).getByText('Source 2')).toBeInTheDocument()

    const toggle = within(others).getByRole('button', { name: 'Show more' })
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(toggle).toHaveTextContent('Show less')
  })

  it('shows a clear state when nothing relevant was found', async () => {
    mockFetch(() =>
      jsonResponse({ ...RESPONSE, answer: "I couldn't find anything about that in your saved content.", sources: [], model: null }),
    )
    const user = setup()
    await askQuestion(user)

    expect(await screen.findByText(/No relevant content in your inbox/)).toBeInTheDocument()
    expect(screen.queryByText(/Answered by/)).not.toBeInTheDocument()
  })

  it('shows a notice when the answer was truncated', async () => {
    mockFetch(() => jsonResponse({ ...RESPONSE, truncated: true }))
    const user = setup()
    await askQuestion(user)

    expect(await screen.findByText('The answer was cut off at the length limit.')).toBeInTheDocument()
  })

  it.each([
    [503, 'ai_not_configured', 'Embeddings are not configured: set EMBEDDING_API_KEY in backend/.env'],
    [502, 'llm_failed', 'Gemini rate limit reached, try again shortly'],
  ])('shows the backend message for a %i error', async (status, code, message) => {
    mockFetch(() => jsonResponse({ error: { code, message } }, status))
    const user = setup()
    await askQuestion(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('hints when nothing is searchable yet', () => {
    setup(0)

    expect(screen.getByText(/None of your saved items are searchable yet/)).toBeInTheDocument()
  })
})
