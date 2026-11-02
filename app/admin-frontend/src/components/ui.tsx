import type { ComponentProps } from 'react'
import {
  ConfirmModal as SharedConfirmModal,
  ErrorBanner as SharedErrorBanner,
  Pagination as SharedPagination,
  SlideOver as SharedSlideOver,
} from '@hubra/ui'
import { tr } from '@/lang'

export { PageHead, StatGrid, StatTile, Tabs, type TabDef } from '@hubra/ui'
// The shared dialogs and states (docs/design-spec.md); the wrappers below
// only add manage's tr() texts.
export { Card, CardGrid, EmptyState, LoadingSpinner, Modal, PanelField, PanelSection } from '@hubra/ui'

export function Pagination(props: ComponentProps<typeof SharedPagination>) {
  return (
    <SharedPagination
      rangeLabel={(start, end, total) => `${start}–${end} ${tr('von', 'of')} ${total}`}
      labels={{
        perPage: tr('Einträge pro Seite', 'Rows per page'),
        first: tr('Erste Seite', 'First page'),
        previous: tr('Vorherige Seite', 'Previous page'),
        next: tr('Nächste Seite', 'Next page'),
        last: tr('Letzte Seite', 'Last page'),
      }}
      {...props}
    />
  )
}

export function SlideOver(props: ComponentProps<typeof SharedSlideOver>) {
  return <SharedSlideOver closeLabel={tr('Schliessen', 'Close')} {...props} />
}

export function ConfirmModal(props: ComponentProps<typeof SharedConfirmModal>) {
  return (
    <SharedConfirmModal confirmLabel={tr('Löschen', 'Delete')} cancelLabel={tr('Abbrechen', 'Cancel')} {...props} />
  )
}

export function ErrorBanner(props: ComponentProps<typeof SharedErrorBanner>) {
  return <SharedErrorBanner retryLabel={tr('Nochmals versuchen', 'Try again')} {...props} />
}
