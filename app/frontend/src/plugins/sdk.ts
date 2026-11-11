/**
 * What a plugin's frontend can use from the app, as `@hubra/plugin-sdk`.
 *
 * Plugins are built against this file and run against the copy the app
 * puts on `window.HubraPluginHost.sdk`, so only add to it; renaming or
 * removing something breaks plugins that are already published.
 */
export { registerPlugin } from './store'
export type {
  PluginDefinition,
  PluginRoute,
  PluginSearch,
  PluginSlotEntry,
  PluginTab,
  PluginWidget,
  SearchHit,
  SlotProps,
} from './types'
export { getCurrentLanguage, useT } from '@/locales/i18n'
export { useAuth, useNav, useToast } from '@/context/AppContext'
export { useModules } from '@/modules/useModules'
export {
  ActionButtons,
  CardGrid,
  CardItem,
  ConfirmModal,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  LoadingSpinner,
  Modal,
  PageHead,
  Pagination,
  Seg,
  SimpleList,
  StatTile,
  Tabs,
  Toggle,
  usePagination,
  useSubmitOnce,
} from '@/components/ui'
export { MemberAddSearch, PanelMemberRow } from '@/components/display'
export { PanelField, PanelSection, SlideOver } from '@/components/feedback'
export {
  DetailBack,
  DetailEmpty,
  DetailFact,
  DetailHeader,
  DetailIcon,
  DetailNotFound,
  DetailRow,
  DetailSection,
  RecordActivity,
} from '@/components/detail'
export { useInvoices } from '@/data/lists'
export { MemberPicker } from '@/components/MemberPicker'
export { useMemberSearch } from '@/data/members'
export { PluginSlot } from './slot'
export { MarkdownRenderer } from '@/components/MarkdownRenderer'
export { formatCHF, formatCHFWhole, formatDate, formatDateTime } from '@/format'
export { BASE, apiFetch, apiFetchRaw } from '@hubra/api-client'
export { listMembers } from '@/api/members'
export { listInvoices, listTxCategories } from '@/api/finance'
export { getConnectionOptions, updateConnection } from '@/api/apps'
export type { Connection } from '@/api/apps'
export { categoryColors, colorText } from '@hubra/ui'
// Date, date-time and time fields with dd.mm.yyyy and 24 hours (same
// string values as type="date", "datetime-local" and "time" inputs).
export { DateField, DateTimeField, TimeField } from '@hubra/ui'
