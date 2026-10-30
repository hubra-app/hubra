import {
  Modal as MantineModal,
  Drawer,
  Text,
  Group,
  Stack,
  Divider,
  Center,
  Loader,
  Alert,
  Button,
  ActionIcon,
  ThemeIcon,
} from '@mantine/core'
import { IconX, IconAlertTriangle, IconRefresh, IconInbox, IconTrash } from '@tabler/icons-react'
import { useMediaQuery } from '@mantine/hooks'
import { useT } from '@/locales/i18n'
import type { FormEvent, ReactNode } from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: string
  wide?: boolean
  children: ReactNode
  footer?: ReactNode
  /**
   * Makes the dialog a form: Enter in a field submits it, and so does a
   * `type="submit"` button in the footer.
   */
  onSubmit?: (event?: FormEvent<HTMLFormElement>) => void
}
export function Modal({
  open,
  onClose,
  title,
  subtitle,
  wide,
  children,
  footer,
  onSubmit,
}: ModalProps) {
  const body = (
    <>
      <Stack gap="sm">{children}</Stack>
      {footer && (
        <>
          <Divider my="sm" />
          <Group justify="flex-end" gap="xs">
            {footer}
          </Group>
        </>
      )}
    </>
  )
  return (
    <MantineModal
      opened={open}
      onClose={onClose}
      title={
        <div>
          <Text fw={700} fz="md">
            {title}
          </Text>
          {subtitle && (
            <Text fz="sm" c="dimmed" mt={2}>
              {subtitle}
            </Text>
          )}
        </div>
      }
      size={wide ? 'lg' : 'md'}
      padding="md"
    >
      {onSubmit ? (
        <form noValidate onSubmit={onSubmit}>
          {body}
        </form>
      ) : (
        body
      )}
    </MantineModal>
  )
}

/**
 * The one side panel layout (notifications, groups, functions, tiers,
 * inventory items): a header with icon, title, subtitle and actions, a
 * scrolling body and an optional footer. Full width on phones.
 */
export function SlideOver({
  title,
  subtitle,
  icon,
  actions,
  width = 420,
  opened = true,
  padded = true,
  onClose,
  children,
  footer,
}: {
  title: ReactNode
  subtitle?: ReactNode
  icon?: ReactNode
  /** Buttons shown in the header before the close button. */
  actions?: ReactNode
  width?: number
  opened?: boolean
  /** false: the body's sections bring their own padding (PanelSection). */
  padded?: boolean
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  const { t } = useT()
  const phone = useMediaQuery('(max-width: 36em)')
  return (
    <Drawer.Root
      opened={opened}
      onClose={onClose}
      position="right"
      size={phone ? '100%' : width}
      padding={0}
      styles={{ content: { display: 'flex', flexDirection: 'column' } }}
    >
      <Drawer.Overlay />
      <Drawer.Content>
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--hb-border)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            flexShrink: 0,
          }}
        >
          {icon && <div style={{ flexShrink: 0, display: 'flex' }}>{icon}</div>}
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Drawer.Title names the dialog for screen readers. */}
            <Drawer.Title
              fw={700}
              fz="md"
              lh={1.35}
              style={{ color: 'var(--hb-text)', overflowWrap: 'anywhere' }}
            >
              {title}
            </Drawer.Title>
            {subtitle && (
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: 'var(--hb-text-3)',
                  marginTop: 2,
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
          <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
            {actions}
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={onClose}
              aria-label={t('common.close')}
            >
              <IconX size={18} />
            </ActionIcon>
          </Group>
        </div>
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            padding: padded ? '16px 20px' : 0,
          }}
        >
          {children}
        </div>
        {footer && (
          <div
            style={{
              padding: '12px 20px',
              borderTop: '1px solid var(--hb-border)',
              flexShrink: 0,
            }}
          >
            {footer}
          </div>
        )}
      </Drawer.Content>
    </Drawer.Root>
  )
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

/** A block of a side panel with an optional small heading. */
export function PanelSection({
  label,
  right,
  border = true,
  children,
}: {
  label?: ReactNode
  /** Shown at the end of the heading row (a count, a small button). */
  right?: ReactNode
  border?: boolean
  children: ReactNode
}) {
  return (
    <section
      style={{
        padding: '16px 20px',
        borderBottom: border ? '1px solid var(--hb-border)' : undefined,
      }}
    >
      {(label || right) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            marginBottom: 10,
          }}
        >
          <div
            style={{
              fontSize: 'var(--mantine-font-size-xs)',
              fontWeight: 600,
              color: 'var(--hb-text-3)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            {label}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  )
}

/** A label above a value, for the facts of an item. */
export function PanelField({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div
        style={{
          fontSize: 'var(--mantine-font-size-xs)',
          color: 'var(--hb-text-3)',
          marginBottom: 2,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 'var(--mantine-font-size-sm)',
          color: 'var(--hb-text)',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        {children}
      </div>
    </div>
  )
}

export function ConfirmModal({
  open,
  title,
  body,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  body?: string
  onConfirm: () => void
  onClose: () => void
}) {
  const { t } = useT()
  return (
    <MantineModal opened={open} onClose={onClose} title={title} size="sm" centered>
      {body && (
        <Text size="sm" c="dimmed" lh={1.6}>
          {body}
        </Text>
      )}
      <Group justify="flex-end" gap="xs" mt="md">
        <Button variant="default" onClick={onClose}>
          {t('common.cancel', 'Abbrechen')}
        </Button>
        <Button
          variant="light"
          color="red"
          leftSection={<IconTrash size={14} />}
          onClick={() => {
            onConfirm()
            onClose()
          }}
        >
          {t('common.delete', 'Löschen')}
        </Button>
      </Group>
    </MantineModal>
  )
}

export function LoadingSpinner({ message, compact }: { message?: string; compact?: boolean }) {
  return (
    <Center mih={compact ? 200 : '60vh'}>
      <Stack align="center" gap="xs">
        <Loader size={compact ? 'md' : 'sm'} />
        {message && (
          <Text size="sm" c="dimmed">
            {message}
          </Text>
        )}
      </Stack>
    </Center>
  )
}

export function ErrorBanner({
  message,
  onRetry,
  onDismiss,
}: {
  message: string
  onRetry?: () => void
  onDismiss?: () => void
}) {
  const { t } = useT()
  return (
    <Alert
      color="red"
      variant="light"
      icon={<IconAlertTriangle size={16} />}
      my="md"
      withCloseButton={!!onDismiss}
      onClose={onDismiss}
    >
      <Group gap="xs" align="center">
        <Text size="sm" flex={1}>
          {message}
        </Text>
        {onRetry && (
          <Button
            variant="subtle"
            size="xs"
            color="red"
            leftSection={<IconRefresh size={13} />}
            onClick={onRetry}
          >
            {t('common.retry', 'Nochmals versuchen')}
          </Button>
        )}
      </Group>
    </Alert>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: { label: string; onClick: () => void }
}) {
  return (
    <Center py={56} px="md">
      <Stack align="center" gap={6}>
        <ThemeIcon size={52} radius="xl" variant="light" color="acc" mb={6}>
          {icon ?? <IconInbox size={26} stroke={1.6} />}
        </ThemeIcon>
        <Text fw={700} fz="md" ta="center">
          {title}
        </Text>
        {description && (
          <Text size="sm" c="dimmed" maw={420} ta="center">
            {description}
          </Text>
        )}
        {action && (
          <Button mt="sm" onClick={action.onClick}>
            {action.label}
          </Button>
        )}
      </Stack>
    </Center>
  )
}

export function Toasts() {
  return null
}
