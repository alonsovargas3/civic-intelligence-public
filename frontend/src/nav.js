// Static tabs require a reviewed baked payload. Keep unsupported features
// visible but disabled with an explanation.
export const ALL_TABS = [
  { value: 'data', label: 'Data' },
  { value: 'stories', label: 'Stories' },
  { value: 'methods', label: 'Methods' },
  { value: 'equity', label: 'Equity' },
  { value: 'owners', label: 'Ownership' },
  { value: 'council', label: 'Council' },
]

const REASONS = {
  equity: 'Equity flags are unavailable in this static edition; no flags payload is baked.',
  owners: 'Ownership is unavailable because its static payload is missing or incomplete.',
  council: 'Council sponsorship is unavailable because its static payload is missing or incomplete.',
  methods: 'Methods are unavailable because their static payload is missing.',
}

export const visibleTabs = (isStatic, features = {}) => ALL_TABS.map((tab) => {
  if (!isStatic) return tab
  const disabled = tab.value === 'equity' ||
    (['owners', 'council', 'methods'].includes(tab.value) && !features[tab.value])
  return disabled ? { ...tab, disabled: true, reason: REASONS[tab.value] } : tab
})
