import { describe, expect, it } from 'vitest'
import { splitCitations } from './citations'

const IDS = new Set([1, 2, 3])

describe('splitCitations', () => {
  it('returns plain text unchanged', () => {
    expect(splitCitations('No citations here.', IDS)).toEqual([{ type: 'text', text: 'No citations here.' }])
  })

  it('splits single, adjacent and grouped citations', () => {
    expect(splitCitations('RAG retrieves [1]. Both agree [2][1]. Combined [1, 3].', IDS)).toEqual([
      { type: 'text', text: 'RAG retrieves ' },
      { type: 'cite', id: 1 },
      { type: 'text', text: '. Both agree ' },
      { type: 'cite', id: 2 },
      { type: 'cite', id: 1 },
      { type: 'text', text: '. Combined ' },
      { type: 'cite', id: 1 },
      { type: 'cite', id: 3 },
      { type: 'text', text: '.' },
    ])
  })

  it('keeps unknown citation numbers as text', () => {
    expect(splitCitations('Made up [9], real [1].', IDS)).toEqual([
      { type: 'text', text: 'Made up [9], real ' },
      { type: 'cite', id: 1 },
      { type: 'text', text: '.' },
    ])
  })

  it('ignores brackets that are not citations', () => {
    expect(splitCitations('See [note] and [1a].', IDS)).toEqual([{ type: 'text', text: 'See [note] and [1a].' }])
  })

  it('handles citations at the very start and end', () => {
    expect(splitCitations('[2] starts and ends [3]', IDS)).toEqual([
      { type: 'cite', id: 2 },
      { type: 'text', text: ' starts and ends ' },
      { type: 'cite', id: 3 },
    ])
  })
})
