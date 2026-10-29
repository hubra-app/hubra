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
import {
  IconX,
  IconAlertTriangle,
  IconRefresh,
  IconInbox,
  IconTrash,
} from '@tabler/icons-react'
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

export function SlideOver({
  title,
  subtitle,
  icon,
  width = 420,
  onClose,
  children,
}: {
  title: string
  subtitle?: string
  icon?: ReactNode
  width?: number
  onClose: () => void
  children: ReactNode
}) {
  const { t } = useT()
  return (
    <Drawer
      opened
      onClose={onClose}
      position="right"
      size={width}
      withCloseButton={false}
      padding={0}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
        }}
      >
        <div
          style={{
            padding: 'var(--mantine-spacing-md)',
            borderBottom: '1px solid var(--mantine-color-gray-3)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mantine-spacing-sm)',
            flexShrink: 0,
          }}
        >
          {icon && <div style={{ flexShrink: 0 }}>{icon}</div>}
          <div style={{ flex: 1, minWidth: 0 }}>
            <Text fw={700} fz="md">
              {title}
            </Text>
            {subtitle && (
              <Text size="sm" c="dimmed">
                {subtitle}
              </Text>
            )}
          </div>
          <ActionIcon variant="subtle" onClick={onClose} aria-label={t('common.close')}>
            <IconX size={16} />
          </ActionIcon>
        </div>
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            padding: '0 var(--mantine-spacing-md)',
            minHeight: 0,
          }}
        >
          {children}
        </div>
      </div>
    </Drawer>
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
    <MantineModal
      opened={open}
      onClose={onClose}
      title={title}
      size="sm"
      centered
    >
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

export function LoadingSpinner({
  message,
  compact,
}: {
  message?: string
  compact?: boolean
}) {
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
