import { describe, it, expect } from 'vitest'
import { staticPath } from './api.js'
import pairs from '../../tests/fixtures/static_slug_pairs.json'

describe('staticPath', () => {
  it.each(pairs)('maps $url -> $path', ({ url, path }) => {
    expect(staticPath(url)).toBe(path)
  })
})
