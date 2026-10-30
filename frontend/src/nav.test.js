import { describe, it, expect } from 'vitest'
import { visibleTabs, ALL_TABS } from './nav.js'

describe('visibleTabs', () => {
  it('keeps every tab in live mode', () => {
    expect(visibleTabs(false)).toEqual(ALL_TABS)
    expect(visibleTabs(false).some((t) => t.value === 'equity')).toBe(true)
  })
  it('explains unavailable static tabs without hiding them', () => {
    const tabs = visibleTabs(true, { methods: true, owners: true, council: false })
    expect(tabs).toHaveLength(ALL_TABS.length)
    expect(tabs.find((t) => t.value === 'equity')).toMatchObject({ disabled: true })
    expect(tabs.find((t) => t.value === 'equity').reason).toMatch(/no flags payload/)
    expect(tabs.find((t) => t.value === 'owners').disabled).toBeUndefined()
    expect(tabs.find((t) => t.value === 'council')).toMatchObject({ disabled: true })
  })
})
