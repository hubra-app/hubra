import type { ComponentProps } from 'react'
import { ConfirmModal as SharedConfirmModal } from '@bitsandbricks/ui'
import { tr } from '@/lang'

// The shared page blocks, dialogs and states (@bitsandbricks/ui), in
// manage's language (HubraProvider in main.tsx). Tabs, StatTile, the side
// panel, the pager and the loading state keep Hubra's prop names.
export { PageHead, StatGrid } from '@bitsandbricks/ui'
export { Pagination, SlideOver, StatTile, Tabs, type TabDef } from '@hubra/ui'
export { EmptyState, ErrorBanner, PanelField, PanelSection } from '@bitsandbricks/ui'
export { Card, CardGrid, LoadingSpinner, Modal } from '@hubra/ui'

/** Asks before deleting: the button says "Löschen" unless the screen names its own. */
export function ConfirmModal(props: ComponentProps<typeof SharedConfirmModal>) {
  return <SharedConfirmModal confirmLabel={tr('Löschen', 'Delete')} {...props} />
}
