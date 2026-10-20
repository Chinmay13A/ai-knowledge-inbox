import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { jsonResponse, makeItem, mockFetch } from '../test/fixtures'
import { IngestForm } from './IngestForm'

function setup() {
  const onCreated = vi.fn()
  render(<IngestForm onCreated={onCreated} />)
  return { onCreated, user: userEvent.setup() }
}

describe('IngestForm', () => {
  it('saves a note and clears the input', async () => {
    const created = makeItem({ id: 5 })
    const fetchMock = mockFetch(() => jsonResponse(created, 201))
    const { onCreated, user } = setup()

    await user.type(screen.getByLabelText('Note'), 'Remember the milk')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(String(init.body))).toEqual({ type: 'note', content: 'Remember the milk' })
    expect(onCreated).toHaveBeenCalledWith(created)
    expect(screen.getByLabelText('Note')).toHaveValue('')
  })

  it('switches to URL mode and posts the URL', async () => {
    const fetchMock = mockFetch(() => jsonResponse(makeItem({ source_type: 'url' }), 201))
    const { user } = setup()

    await user.click(screen.getByRole('button', { name: 'URL' }))
    expect(screen.getByRole('button', { name: 'URL' })).toHaveAttribute('aria-pressed', 'true')
    await user.type(screen.getByLabelText('URL'), '  https://example.com/post  ')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      type: 'url',
      url: 'https://example.com/post',
    })
  })

  it.each([
    ['note', '   ', 'Write something first.'],
    ['url', 'not a url', 'Enter a full URL, starting with http:// or https://'],
    ['url', 'ftp://example.com/file', 'Only http:// and https:// links are supported.'],
  ])('rejects invalid %s input without calling the API', async (mode, value, message) => {
    const fetchMock = mockFetch(() => jsonResponse({}, 201))
    const { user } = setup()

    if (mode === 'url') await user.click(screen.getByRole('button', { name: 'URL' }))
    await user.type(screen.getByLabelText(mode === 'url' ? 'URL' : 'Note'), value)
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(screen.getByRole('alert')).toHaveTextContent(message)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows the backend error message', async () => {
    mockFetch(() =>
      jsonResponse(
        { error: { code: 'blocked_by_robots', message: 'This site does not allow automated access to this page (robots.txt)' } },
        422,
      ),
    )
    const { onCreated, user } = setup()

    await user.click(screen.getByRole('button', { name: 'URL' }))
    await user.type(screen.getByLabelText('URL'), 'https://example.com/private')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('does not allow automated access')
    expect(onCreated).not.toHaveBeenCalled()
    expect(screen.getByLabelText('URL')).toHaveValue('https://example.com/private')
  })

  it('submits a note with Ctrl+Enter', async () => {
    const fetchMock = mockFetch(() => jsonResponse(makeItem(), 201))
    const { user } = setup()

    await user.type(screen.getByLabelText('Note'), 'Quick note')
    await user.keyboard('{Control>}{Enter}{/Control}')

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
