import {
  ActionIcon,
  Alert,
  Button,
  Center,
  Divider,
  Drawer,
  Group,
  Loader,
  Modal as MantineModal,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  useMatches,
} from '@mantine/core'
import { IconAlertTriangle, IconInbox, IconRefresh, IconTrash, IconX } from '@tabler/icons-react'
import type { CSSProperties, FormEvent, ReactNode } from 'react'

// Dialogs, side panels, cards and the empty / error / loading states every
// app uses (docs/design-spec.md, sections 3 and 4). Texts default to German;
// each app's wrapper passes its translations.

/** The bordered card every list and form sits in (radius and shadow from the theme). */
export function Card({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <Paper withBorder style={{ overflow: 'hidden', ...style }}>
      {children}
    </Paper>
  )
}

function CardHeader({ title, children, style }: { title?: ReactNode; children?: ReactNode; style?: CSSProperties }) {
  return (
    <Group
      justify="space-between"
      align="center"
      gap="sm"
      px="lg"
      py="md"
      wrap="wrap"
      style={{ borderBottom: '1px solid var(--hb-border)', ...style }}
    >
      {title && (
        <Text fw={700} fz="md" ff="heading">
          {title}
        </Text>
      )}
      {children}
    </Group>
  )
}

Card.Header = CardHeader

export function CardGrid({ children, columns = 3 }: { children: ReactNode; columns?: number }) {
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: columns }} spacing="md">
      {children}
    </SimpleGrid>
  )
}

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
        <>
          {title}
          {subtitle && (
            <Text component="span" display="block" fz="sm" fw={400} ff="text" c="dimmed" mt={2}>
              {subtitle}
            </Text>
          )}
        </>
      }
      size={wide ? 'lg' : 'md'}
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
  closeLabel = 'Schliessen',
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
  /** Screen-reader name of the close button. */
  closeLabel?: string
}) {
  // Full width on phones (below xs, 36em).
  const size = useMatches({ base: '100%', xs: width }, { getInitialValueInEffect: false })
  return (
    <Drawer.Root
      opened={opened}
      onClose={onClose}
      position="right"
      size={size}
      padding={0}
      styles={{
        // Below the top bar, so the bell and the page title stay in view.
        inner: { top: 'var(--hb-header-h, 0px)', height: 'calc(100% - var(--hb-header-h, 0px))' },
        overlay: { top: 'var(--hb-header-h, 0px)' },
        content: {
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          borderLeft: '1px solid var(--hb-border)',
          boxShadow: 'var(--mantine-shadow-lg)',
        },
      }}
    >
      <Drawer.Overlay backgroundOpacity={0.18} />
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
              aria-label={closeLabel}
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
  confirmLabel = 'Löschen',
  cancelLabel = 'Abbrechen',
}: {
  open: boolean
  title: string
  body?: string
  onConfirm: () => void
  onClose: () => void
  /** The action button; 'Löschen' unless the app passes its own. */
  confirmLabel?: string
  cancelLabel?: string
}) {
  return (
    <MantineModal opened={open} onClose={onClose} title={title} size="sm">
      {body && (
        <Text size="sm" c="dimmed" lh={1.6}>
          {body}
        </Text>
      )}
      <Group justify="flex-end" gap="xs" mt="md">
        <Button variant="default" onClick={onClose}>
          {cancelLabel}
        </Button>
        <Button
          color="red"
          leftSection={<IconTrash size={16} />}
          onClick={() => {
            onConfirm()
            onClose()
          }}
        >
          {confirmLabel}
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
  retryLabel = 'Nochmals versuchen',
}: {
  message: string
  onRetry?: () => void
  onDismiss?: () => void
  retryLabel?: string
}) {
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
            leftSection={<IconRefresh size={16} />}
            onClick={onRetry}
          >
            {retryLabel}
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
          {icon ?? <IconInbox size={24} />}
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
