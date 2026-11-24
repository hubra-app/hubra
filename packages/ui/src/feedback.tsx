import { Divider, Group, Modal as MantineModal, Paper, SimpleGrid, Stack, Text } from '@mantine/core'
import type { CSSProperties, FormEvent, ReactNode } from 'react'

// Hubra's card and form dialog (docs/design-spec.md, sections 3 and 4). They
// differ from @bitsandbricks/ui's Card (padded, title prop) and have no
// shared counterpart yet, so plugins keep these. The side panel, empty,
// error and loading states and the confirm dialog are the shared ones.

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
