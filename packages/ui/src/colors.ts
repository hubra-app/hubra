// Hubra Violet. Shade 6 is the light-mode primary, shade 4 the dark-mode one.
export const accColors = [
  '#f5f1ff',
  '#ebe3ff',
  '#d6c7ff',
  '#bba3fd',
  '#9f7cf8',
  '#8758f0',
  '#7441e0',
  '#6131c4',
  '#4d27a0',
  '#3a1e78',
] as const

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

// Brand neutrals (violet-tinted). Shade 6 is Mantine's 'dimmed' text colour,
// kept at the brand's secondary text colour so it passes WCAG AA on white.
export const grayColors = [
  '#f7f6fb',
  '#f1eff7',
  '#ebe8f2',
  '#e6e3ef',
  '#d6d2e3',
  '#b7b0c9',
  '#5e5873',
  '#4a4560',
  '#2e2940',
  '#1a1625',
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

// Success: paid, active, passed. Shade 6 is the brand value (brand/README.md).
export const greenColors = [
  '#edf4f1',
  '#d5e7df',
  '#accfbf',
  '#82b79f',
  '#599f80',
  '#348963',
  '#18794e',
  '#146742',
  '#115537',
  '#0d432b',
] as const

// Warning: due, needs a look. Dark text on fills (autoContrast). Shade 6 is the brand value (brand/README.md).
export const orangeColors = [
  '#fdf8ec',
  '#fbeed5',
  '#f7deab',
  '#f3cd82',
  '#eebd58',
  '#ebae33',
  '#e8a317',
  '#c58b14',
  '#a27210',
  '#805a0d',
] as const

// Danger: overdue, failed, delete. Shade 6 is the brand value (brand/README.md).
export const redColors = [
  '#fbeff1',
  '#f5dbe0',
  '#ebb6c0',
  '#e192a0',
  '#d76e81',
  '#ce4d65',
  '#c73550',
  '#a92d44',
  '#8b2538',
  '#6d1d2c',
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
