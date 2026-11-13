// A group of platform settings that needs nothing but its fields: one file per
// group in this folder (`export default defineSettings(...)`), so pull
// requests that add settings to different pages don't edit the same file.
// SettingsSection draws it as a card: title, description, the fields and a
// reset button. Groups with their own buttons or layout stay in
// SettingsSection.tsx.

export interface SettingsGroup {
  /** What `<SettingsSection section="…" />` names. */
  id: string
  /** The keys this group shows and saves, in order. */
  keys: string[]
  /** Keys whose default is built into Hubra, not read from the environment. */
  builtIn?: string[]
  title: () => string
  desc: () => string
  /** The backend describes the settings in English: German label and help. */
  de?: Record<string, [string, string]>
}

export function defineSettings(group: SettingsGroup): SettingsGroup {
  return group
}

export const SETTINGS_GROUPS: Record<string, SettingsGroup> = Object.fromEntries(
  Object.entries(
    import.meta.glob<SettingsGroup>(['./*.ts', '!./registry.ts'], { eager: true, import: 'default' }),
  ).map(([, group]) => [group.id, group]),
)
