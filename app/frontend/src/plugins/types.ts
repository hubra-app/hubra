import type { ComponentType } from 'react'

/** Shown only while `module` is on for the club and the user has `perm`. */
interface Gated {
  module: string
  perm?: string
  order?: number
}

/** A screen of its own, under /<club>/app/<path>. */
export interface PluginRoute extends Gated {
  path: string
  component: ComponentType
}

/** A tab on a screen of the app, such as `finance`. */
export interface PluginTab extends Gated {
  screen: string
  id: string
  /** A translation key. */
  label: string
  component: ComponentType
}

/** A component the app renders at one of its slots (see `PluginSlot`). */
export interface PluginSlotEntry extends Gated {
  slot: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: ComponentType<any>
}

export interface PluginDefinition {
  /** The plugin's id, as in its plugin.yaml. */
  id: string
  routes?: PluginRoute[]
  tabs?: PluginTab[]
  slots?: PluginSlotEntry[]
  /** Icons the plugin's sidebar entries name, by the name in its module manifest. */
  icons?: Record<string, ComponentType<{ size?: number }>>
  /** Translations by language (`en-GB`, `de-CH`), nested like translation.json. */
  translations?: Record<string, Record<string, unknown>>
}

/** Props each slot passes to what is registered there. */
export interface SlotProps {
  'account.cards': Record<string, never>
  'inventory.item': { itemId: number }
  'settings.module.actions': { code: string; configured: boolean; name: string }
}
