/**
 * What a plugin's frontend can use from the app, as `@hubra/plugin-sdk`.
 *
 * Plugins are built against this file and run against the copy the app
 * puts on `window.HubraPluginHost.sdk`, so only add to it; renaming or
 * removing something breaks plugins that are already published.
 */
export { registerPlugin } from './store'
export type { PluginDefinition, PluginRoute, PluginSlotEntry, PluginTab, SlotProps } from './types'
export { useT } from '@/locales/i18n'
export { useAuth, useToast } from '@/context/AppContext'
export { useModules } from '@/modules/useModules'
export {
  ConfirmModal,
  DataTable,
  Field,
  Modal,
  PageHead,
  Tabs,
  Toggle,
  usePagination,
} from '@/components/ui'
export { MarkdownRenderer } from '@/components/MarkdownRenderer'
export { formatCHF, formatDateTime } from '@/format'
export { BASE, apiFetch, apiFetchRaw } from '@hubra/api-client'
export { listMembers } from '@/api/members'
export { listInvoices, listTxCategories } from '@/api/finance'
export { getConnectionOptions, updateConnection } from '@/api/apps'
export type { Connection } from '@/api/apps'
