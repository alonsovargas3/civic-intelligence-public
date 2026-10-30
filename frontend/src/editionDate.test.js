import { describe, it, expect } from 'vitest'
import { editionDate } from './editionDate.js'

describe('editionDate', () => {
  it('converts a UTC version stamp to the Austin date', () => {
    // 01:52Z on Oct 9 is the evening of Oct 8 in Austin.
    expect(editionDate('v=20261009T015201Z')).toBe('2026-10-08')
    expect(editionDate('v=20261009T120000Z')).toBe('2026-10-09')
  })
  it('returns null for frozen editions and junk', () => {
    expect(editionDate('edition:atx_civic_full_20260711')).toBeNull()
    expect(editionDate(undefined)).toBeNull()
    expect(editionDate('')).toBeNull()
  })
})
