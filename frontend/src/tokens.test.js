import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const css = readFileSync(fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf8')

describe('design tokens', () => {
  it('uses the warm cream canvas and warm hairline', () => {
    expect(css).toMatch(/--canvas:\s*#f6f4ef/)
    expect(css).toMatch(/--hairline:\s*#e6e2da/)
    expect(css).toMatch(/--ink:\s*#262a33/)
  })
  it('defines the coral interactive accent family', () => {
    expect(css).toMatch(/--accent:\s*#F77660/i)
    expect(css).toMatch(/--accent-deep:\s*#d95a45/i)
    expect(css).toMatch(/--accent-ink:/)
    expect(css).toMatch(/--accent-tint:/)
  })
  it('defines the slate band + warm secondary tokens', () => {
    expect(css).toMatch(/--slate:\s*#3e4a61/i)
    expect(css).toMatch(/--on-slate:/)
    expect(css).toMatch(/--amber:\s*#FEAF56/i)
    expect(css).toMatch(/--orange:\s*#EA8253/i)
    expect(css).toMatch(/--sage:\s*#BDD0C1/i)
    expect(css).toMatch(/--slate-blue:\s*#818CA0/i)
  })
  it('keeps the brand-critical Blues ramp', () => {
    expect(css).toMatch(/--blue-6:\s*#2171b5/)
    expect(css).toMatch(/--blue-8:\s*#08306b/)
  })
})
