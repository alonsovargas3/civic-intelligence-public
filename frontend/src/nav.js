// Dashboard sidebar tabs. In the static build the Equity tab is removed (its
// <Flags/> panel needs the live /v1 API); the tab definition is kept here so
// flipping VITE_STATIC off restores it with no code change.
export const ALL_TABS = [
  { value: 'data', label: 'Data' },
  { value: 'stories', label: 'Stories' },
  { value: 'methods', label: 'Methods' },
  { value: 'equity', label: 'Equity' },
  { value: 'owners', label: 'Ownership' },
  { value: 'council', label: 'Council' },
]

export const visibleTabs = (isStatic) =>
  isStatic ? ALL_TABS.filter((t) => t.value !== 'equity') : ALL_TABS
