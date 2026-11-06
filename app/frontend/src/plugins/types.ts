import type { ComponentType } from 'react'
import type { Connection } from '@/api/apps'
import type { Invoice } from '@/types'

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
  /**
   * The page tab this one sits under as a sub-tab, if the screen groups its
   * tabs. On `finance`: `bookings`, `planning` or `setup`. Without it the
   * tab is a page tab of its own.
   */
  group?: string
}

/** A component the app renders at one of its slots (see `PluginSlot`). */
export interface PluginSlotEntry extends Gated {
  slot: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: ComponentType<any>
}

/** One thing a plugin's search found; matched on `label`, `sub` and `keywords`. */
export interface SearchHit {
  id: string | number
  label: string
  sub?: string
  /** Club-app path, such as `/app/inventory/12`. */
  path: string
  /** More text to match, not shown. */
  keywords?: string
}

/** A list the global search (Ctrl+K) looks through. */
export interface PluginSearch extends Gated {
  id: string
  /** A translation key: the label shown on each hit, such as "Inventar". */
  label: string
  color?: { bg: string; color: string }
  /** Loaded once the search is first used, then kept for a minute. */
  load: () => Promise<SearchHit[]>
}

/**
 * A widget members can put on their own dashboards (Dashboard › +). Stored
 * as type `p:<plugin id>.<id>`; `config` is what the member set in the
 * widget's fields.
 */
export interface PluginWidget extends Gated {
  id: string
  /** Translation keys: the widget's name and one line on what it shows. */
  label: string
  description?: string
  /** Default width: s (a third), m (half), l (full). */
  size?: 's' | 'm' | 'l'
  /** Settings the member fills in when adding it. */
  fields?: {
    key: string
    /** A translation key. */
    label: string
    kind: 'text' | 'number' | 'switch'
    default?: string | number | boolean
  }[]
  /**
   * The backend widget contract this component draws (a `widget_contract`
   * with `view="custom"`, docs/contracts.md). The widget is then offered as
   * that contract (type `w:<contract>`), and the component gets the data its
   * handler read for the viewer as `data`. Without it, the widget is the
   * plugin's own (type `p:<plugin>.<id>`) and loads its data itself.
   */
  contract?: string
  component: ComponentType<{
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    config: Record<string, any>
    size: 's' | 'm' | 'l'
    data?: unknown
  }>
}

export interface PluginDefinition {
  /** The plugin's id, as in its plugin.yaml. */
  id: string
  routes?: PluginRoute[]
  tabs?: PluginTab[]
  slots?: PluginSlotEntry[]
  search?: PluginSearch[]
  /** Widgets for members' own dashboards. */
  widgets?: PluginWidget[]
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
  /** In a connected app's details (Einstellungen › Verbundene Apps); check `connection.provider`. */
  'apps.connection': { connection: Connection; onChange: () => void }
  /** Next to an invoice's buttons: the member's open invoices (Konto) and the invoice page. */
  'invoice.actions': { invoice: Invoice; onChange: () => void }
  /** More tiles in the club overview's numbers row (Dashboard › Übersicht); render a `StatTile`. */
  'dashboard.stats': Record<string, never>
  /** Cards under Finanzen › Einstellungen › Abrechnung: the finance module's settings, and saving some of them (the rest are kept). */
  'finance.settings': {
    config: Record<string, unknown>
    save: (values: Record<string, string | number | boolean | null>) => Promise<void>
    busy: boolean
  }
}
