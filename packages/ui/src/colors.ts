// Colours only Hubra has. The greys, the status colours and the accent come
// from @bitsandbricks/tokens; Hubra's accent is set in theme.ts.

// Signal Gold: the logo dot, 'new' and 'due' markers. Always with dark text.
export const goldColors = [
  '#fffbeb',
  '#fff3c4',
  '#fce588',
  '#fbd936',
  '#fece2b',
  '#fec50f',
  '#ecbb00',
  '#d4a000',
  '#8a6a00',
  '#5c4700',
] as const

export const pinkColors = [
  '#fff0f6',
  '#ffdbe9',
  '#ffb3cf',
  '#ff8db5',
  '#fe64ac',
  '#fd4c9d',
  '#e03f8b',
  '#c23578',
  '#9c2a60',
  '#7a2149',
] as const

// Category colours: tags, tiers, event types, inventory types, search result
// types. The same palette new accounts get their avatar colour from
// (app/backend/hubra/core/avatar.py). Clubs can pick their own colours for
// tiers, groups and finance categories; these are the defaults.
export const categoryColors = {
  blue: '#2596be',
  royal: '#1f61d8',
  pink: '#fe64ac',
  navy: '#1c2740',
  slate: '#8e97a7',
  red: '#ff4d3d',
  green: '#1f9d57',
  orange: '#f39c12',
  purple: '#9b59b6',
  yellow: '#fece2b',
} as const
