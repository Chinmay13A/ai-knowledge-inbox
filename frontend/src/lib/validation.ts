import { MAX_NOTE_CHARS, MAX_QUESTION_CHARS } from '../api/types'

// Instant feedback only: the backend validates everything again.

export function validateNote(content: string): string | null {
  if (!content.trim()) return 'Write something first.'
  if (content.trim().length > MAX_NOTE_CHARS) {
    return `Notes can be at most ${MAX_NOTE_CHARS.toLocaleString()} characters.`
  }
  return null
}

export function validateUrl(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return 'Paste a link first.'
  let url: URL
  try {
    url = new URL(trimmed)
  } catch {
    return 'Enter a full URL, starting with http:// or https://'
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return 'Only http:// and https:// links are supported.'
  return null
}

export function validateQuestion(question: string): string | null {
  if (!question.trim()) return 'Type a question first.'
  if (question.trim().length > MAX_QUESTION_CHARS) {
    return `Questions can be at most ${MAX_QUESTION_CHARS.toLocaleString()} characters.`
  }
  return null
}
