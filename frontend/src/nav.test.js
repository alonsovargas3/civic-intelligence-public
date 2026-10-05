import { describe, it, expect } from 'vitest'
import { visibleTabs, ALL_TABS } from './nav.js'

describe('visibleTabs', () => {
  it('keeps every tab in live mode', () => {
    expect(visibleTabs(false)).toEqual(ALL_TABS)
    expect(visibleTabs(false).some((t) => t.value === 'equity')).toBe(true)
  })
  it('drops the equity tab in static mode', () => {
    const tabs = visibleTabs(true)
    expect(tabs.some((t) => t.value === 'equity')).toBe(false)
    expect(tabs.some((t) => t.value === 'data')).toBe(true)
    expect(tabs).toHaveLength(ALL_TABS.length - 1)
  })
})
