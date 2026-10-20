import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { MAX_QUESTION_CHARS } from '../api/types'
import { useAsk } from '../hooks/useAsk'
import { validateQuestion } from '../lib/validation'
import { AnswerView } from './AnswerView'
import { ErrorBanner } from './ErrorBanner'

interface AskPanelProps {
  readyCount: number // saved items that are searchable (status "ready")
}

export function AskPanel({ readyCount }: AskPanelProps) {
  const [question, setQuestion] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const { result, asking, error, ask } = useAsk()

  const handleSubmit = (event?: FormEvent) => {
    event?.preventDefault()
    const problem = validateQuestion(question)
    setValidationError(problem)
    if (!problem) void ask(question.trim())
  }

  // Enter asks; Shift+Enter adds a new line.
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      handleSubmit()
    }
  }

  const message = validationError ?? error

  return (
    <section aria-labelledby="ask-heading" className="h-fit rounded-lg border border-gray-200 bg-white p-4 lg:sticky lg:top-6">
      <h2 id="ask-heading" className="mb-3 font-medium">
        Ask a question
      </h2>

      {readyCount === 0 && (
        <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          None of your saved items are searchable yet. Add content, and once it shows Ready you can ask about it.
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-2">
        <label htmlFor="question-input" className="sr-only">
          Question
        </label>
        <textarea
          id="question-input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
          placeholder="e.g. What did I save about retrieval-augmented generation?"
          className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-200"
        />
        <div className="flex items-center justify-between gap-3">
          <span className={`text-xs ${question.length > MAX_QUESTION_CHARS ? 'text-red-700' : 'text-gray-500'}`}>
            Enter to ask · Shift + Enter for a new line · {question.length.toLocaleString()} /{' '}
            {MAX_QUESTION_CHARS.toLocaleString()}
          </span>
          <button
            type="submit"
            disabled={asking}
            className="rounded-md bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400"
          >
            {asking ? 'Thinking…' : 'Ask'}
          </button>
        </div>
        <div aria-live="polite">{message && <ErrorBanner message={message} />}</div>
      </form>

      <div aria-live="polite" aria-busy={asking} className="mt-4">
        {asking && (
          <div className="mb-4 space-y-2">
            <p className="text-sm text-gray-600">Searching your inbox and writing an answer…</p>
            <div className="h-4 w-3/4 animate-pulse rounded bg-gray-100" />
            <div className="h-4 w-1/2 animate-pulse rounded bg-gray-100" />
          </div>
        )}
        {result && (
          <div className={asking ? 'opacity-50' : ''}>
            <AnswerView result={result} />
          </div>
        )}
      </div>
    </section>
  )
}
