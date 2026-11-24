import { Button, Group, Text } from '@mantine/core'
import { ConfirmModal as SharedConfirmModal } from '@bitsandbricks/ui'
import type { ComponentProps } from 'react'
import { useT } from '@/locales/i18n'

// The dialogs, side panel and states are the shared @bitsandbricks/ui ones;
// their words come from the club app's texts (BrandedMantineProvider). The
// side panel and loading state keep Hubra's names for screens and plugins.
export { EmptyState, ErrorBanner, PanelField, PanelSection } from '@bitsandbricks/ui'
export { LoadingSpinner, Modal, SlideOver } from '@hubra/ui'

/** Asks before deleting: the button says "Löschen" unless the screen names its own. */
export function ConfirmModal(props: ComponentProps<typeof SharedConfirmModal>) {
  const { t } = useT()
  return <SharedConfirmModal confirmLabel={t('common.delete', 'Löschen')} {...props} />
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
