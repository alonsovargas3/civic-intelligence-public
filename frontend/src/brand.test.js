import { describe, it, expect } from 'vitest'
import { BRAND_NAME, BRAND_DOMAIN, BRAND_TAGLINE } from './brand.js'

describe('brand constants', () => {
  it('is ATX Civic Data', () => {
    expect(BRAND_NAME).toBe('ATX Civic Data')
    expect(BRAND_DOMAIN).toBe('example.org')
    expect(BRAND_TAGLINE).toBe('Research, not advocacy')
  })
})
