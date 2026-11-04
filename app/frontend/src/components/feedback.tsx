import { Button, Group, Text } from '@mantine/core'
import {
  ConfirmModal as SharedConfirmModal,
  ErrorBanner as SharedErrorBanner,
  SlideOver as SharedSlideOver,
} from '@hubra/ui'
import type { ComponentProps } from 'react'
import { useT } from '@/locales/i18n'

// The shared dialogs and states live in @hubra/ui; these wrappers only add
// the club app's translations.
export { EmptyState, LoadingSpinner, Modal, PanelField, PanelSection } from '@hubra/ui'

export function SlideOver(props: ComponentProps<typeof SharedSlideOver>) {
  const { t } = useT()
  return <SharedSlideOver closeLabel={t('common.close')} {...props} />
}

export function ConfirmModal(props: ComponentProps<typeof SharedConfirmModal>) {
  const { t } = useT()
  return (
    <SharedConfirmModal
      confirmLabel={t('common.delete', 'Löschen')}
      cancelLabel={t('common.cancel', 'Abbrechen')}
      {...props}
    />
  )
}

export function ErrorBanner(props: ComponentProps<typeof SharedErrorBanner>) {
  const { t } = useT()
  return <SharedErrorBanner retryLabel={t('common.retry', 'Nochmals versuchen')} {...props} />
}

/** Above a list that shows only the entry a link pointed at. */
export function LinkedEntryBar({ label, onShowAll }: { label: string; onShowAll: () => void }) {
  const { t } = useT()
  return (
    <Group
      justify="space-between"
      gap="sm"
      wrap="nowrap"
      mb="md"
      px="md"
      py={8}
      style={{
        borderRadius: 'var(--mantine-radius-md)',
        background: 'var(--mantine-color-acc-light)',
      }}
    >
      <Text fz="sm" style={{ color: 'var(--hb-text)' }}>
        {label}
      </Text>
      <Button size="xs" variant="subtle" onClick={onShowAll} style={{ flexShrink: 0 }}>
        {t('common.showAll', 'Alle anzeigen')}
      </Button>
    </Group>
  )
}

export function Toasts() {
  return null
}
