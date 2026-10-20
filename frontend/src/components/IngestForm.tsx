import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { MAX_NOTE_CHARS, type IngestRequest, type Item } from '../api/types'
import { useIngest } from '../hooks/useIngest'
import { validateNote, validateUrl } from '../lib/validation'
import { ErrorBanner } from './ErrorBanner'

type Mode = 'note' | 'url'

interface IngestFormProps {
  onCreated: (item: Item) => void
}

export function IngestForm({ onCreated }: IngestFormProps) {
  const [mode, setMode] = useState<Mode>('note')
  const [note, setNote] = useState('')
  const [url, setUrl] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const { submit, submitting, error, clearError } = useIngest()

  const switchMode = (next: Mode) => {
    setMode(next)
    setValidationError(null)
    clearError()
  }

  const handleSubmit = async (event?: FormEvent) => {
    event?.preventDefault()
    const problem = mode === 'note' ? validateNote(note) : validateUrl(url)
    setValidationError(problem)
    if (problem) return

    const request: IngestRequest = mode === 'note' ? { type: 'note', content: note } : { type: 'url', url: url.trim() }
    const item = await submit(request)
    if (!item) return
    if (mode === 'note') setNote('')
    else setUrl('')
    onCreated(item)
  }

  const handleNoteKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) void handleSubmit()
  }

  const message = validationError ?? error

  return (
    <section aria-labelledby="add-content-heading" className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 id="add-content-heading" className="mb-3 font-medium">
        Add content
      </h2>

      <div role="group" aria-label="Content type" className="mb-3 inline-flex rounded-md border border-gray-300 p-0.5 text-sm">
        {(['note', 'url'] as const).map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={mode === option}
            onClick={() => switchMode(option)}
            className={`rounded px-3 py-1 ${mode === option ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-100'}`}
          >
            {option === 'note' ? 'Note' : 'URL'}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-3">
        {mode === 'note' ? (
          <div>
            <label htmlFor="note-input" className="sr-only">
              Note
            </label>
            <textarea
              id="note-input"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              onKeyDown={handleNoteKeyDown}
              rows={5}
              placeholder="Write or paste a note…"
              className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-200"
            />
            <p className={`text-right text-xs ${note.length > MAX_NOTE_CHARS ? 'text-red-700' : 'text-gray-500'}`}>
              {note.length.toLocaleString()} / {MAX_NOTE_CHARS.toLocaleString()}
            </p>
          </div>
        ) : (
          <div>
            <label htmlFor="url-input" className="sr-only">
              URL
            </label>
            <input
              id="url-input"
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com/article"
              className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-200"
            />
            <p className="mt-1 text-xs text-gray-500">The page is fetched on the server and its main text is saved.</p>
          </div>
        )}

        <div aria-live="polite">{message && <ErrorBanner message={message} />}</div>

        <div className="flex items-center justify-between gap-3">
          {mode === 'note' ? <span className="text-xs text-gray-500">Ctrl + Enter to save</span> : <span />}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400"
          >
            {submitting ? (mode === 'url' ? 'Fetching page…' : 'Saving…') : 'Save'}
          </button>
        </div>
      </form>
    </section>
  )
}
