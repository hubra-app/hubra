import { useState } from 'react'
import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Loader,
  Menu,
  Modal,
  Paper,
  SegmentedControl,
  Stack,
  Text,
  ThemeIcon,
  UnstyledButton,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  IconAlertTriangle,
  IconBellOff,
  IconChecks,
  IconChevronRight,
  IconCircleCheck,
  IconDots,
  IconInfoCircle,
  IconTrash,
  IconUsers,
  IconX,
} from '@tabler/icons-react'
import {
  fillNotificationText,
  notificationMessageText,
  notificationTitleText,
  safeNotificationLink,
  type NotificationText,
} from '@hubra/ui'
import { useSso } from '@/context/SsoContext'
import { LoadFailed } from '@/components/LoadFailed'
import { getLang, tr } from '@/lang'
import * as authApi from '@/api/auth'
import type { AccountNotification } from '@/api/auth'

type List = Awaited<ReturnType<typeof authApi.getNotifications>>

const KIND = {
  info: { color: 'blue', icon: <IconInfoCircle size={16} /> },
  success: { color: 'green', icon: <IconCircleCheck size={16} /> },
  warning: { color: 'yellow', icon: <IconAlertTriangle size={16} /> },
  member: { color: 'pink', icon: <IconUsers size={16} /> },
} as const

function show(text: NotificationText | null, raw: string): string {
  if (!text) return raw
  const vars = { ...text.vars }
  if (vars.name === 'A member') vars.name = tr('Ein Mitglied', 'A member')
  return fillNotificationText(tr(text.de, text.en), vars)
}

function when(iso: string): string {
  return new Date(iso).toLocaleString(getLang() === 'en' ? 'en-GB' : 'de-CH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

/** The person's notifications from all their clubs. */
export function NotificationsTab() {
  const { urls, notify } = useSso()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const [confirmClear, setConfirmClear] = useState(false)
  const list = useQuery({ queryKey: ['notifications'], queryFn: authApi.getNotifications })

  // Change the list at once, then the server; on failure load it again.
  const update = (change: (prev: List) => List, request: Promise<void>) => {
    queryClient.setQueryData<List>(['notifications'], (prev) => (prev ? change(prev) : prev))
    request.catch(() => queryClient.invalidateQueries({ queryKey: ['notifications'] }))
  }
  const same = (a: AccountNotification, b: AccountNotification) =>
    a.id === b.id && a.club.slug === b.club.slug

  const markRead = (n: AccountNotification) =>
    update(
      (prev) => ({
        data: prev.data.map((x) => (same(x, n) ? { ...x, read: true } : x)),
        meta: { unread: Math.max(0, prev.meta.unread - 1) },
      }),
      authApi.markNotificationRead(n),
    )
  const remove = (n: AccountNotification) =>
    update(
      (prev) => ({
        data: prev.data.filter((x) => !same(x, n)),
        meta: { unread: Math.max(0, prev.meta.unread - (n.read ? 0 : 1)) },
      }),
      authApi.deleteNotification(n),
    )
  const markAllRead = () =>
    update(
      (prev) => ({ data: prev.data.map((x) => ({ ...x, read: true })), meta: { unread: 0 } }),
      authApi.markAllNotificationsRead(),
    )
  const clearRead = () =>
    update(
      (prev) => ({ data: prev.data.filter((x) => !x.read), meta: prev.meta }),
      authApi.clearNotifications(true),
    )
  const clearAll = () =>
    update(() => ({ data: [], meta: { unread: 0 } }), authApi.clearNotifications())

  // Opens the club it came from at the page it is about.
  const open = async (n: AccountNotification) => {
    if (!n.read) markRead(n)
    const link = safeNotificationLink(n.link)
    if (!link || !n.club.slug) return
    try {
      await authApi.switchTenant(n.club.slug)
      window.location.assign(`${urls.cos}/${encodeURIComponent(n.club.slug)}${link}`)
    } catch (err: unknown) {
      if ((err as { code?: string }).code === 'EMAIL_NOT_VERIFIED') {
        navigate('/verify')
        return
      }
      notify(
        'error',
        tr('Der Verein konnte nicht geöffnet werden', 'Could not open the club'),
        err instanceof Error ? err.message : '',
      )
    }
  }

  if (list.isError) return <LoadFailed onRetry={() => list.refetch()} />
  if (!list.data) return <Loader size="sm" />

  const { data: items, meta } = list.data
  const visible = filter === 'unread' ? items.filter((n) => !n.read) : items
  const clubs = new Set(items.map((n) => n.club.slug))

  return (
    <Stack gap="sm">
      <Group justify="space-between" wrap="nowrap">
        <Text size="sm" c="dimmed">
          {meta.unread > 0
            ? tr(`${meta.unread} ungelesen, aus allen deinen Vereinen`, `${meta.unread} unread, from all your clubs`)
            : tr('Alles gelesen. Hier landen die Benachrichtigungen aller deiner Vereine.', 'All read. Notifications from all your clubs land here.')}
        </Text>
        <Group gap={4} wrap="nowrap">
          <Button
            variant="light"
            size="xs"
            leftSection={<IconChecks size={14} />}
            disabled={meta.unread === 0}
            onClick={markAllRead}
          >
            {tr('Alle gelesen', 'Mark all read')}
          </Button>
          <Menu position="bottom-end">
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" aria-label={tr('Weitere Aktionen', 'More actions')}>
                <IconDots size={18} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconTrash size={16} />}
                disabled={!items.some((n) => n.read)}
                onClick={clearRead}
              >
                {tr('Gelesene löschen', 'Delete read')}
              </Menu.Item>
              <Menu.Item
                color="red"
                leftSection={<IconTrash size={16} />}
                disabled={items.length === 0}
                onClick={() => setConfirmClear(true)}
              >
                {tr('Alle löschen', 'Delete all')}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>

      <SegmentedControl
        fullWidth
        size="xs"
        value={filter}
        onChange={(v) => setFilter(v as 'all' | 'unread')}
        data={[
          { value: 'all', label: tr('Alle', 'All') },
          {
            value: 'unread',
            label: meta.unread > 0 ? `${tr('Ungelesen', 'Unread')} (${meta.unread})` : tr('Ungelesen', 'Unread'),
          },
        ]}
      />

      {visible.length === 0 ? (
        <Paper withBorder radius="md" py={40} ta="center" c="dimmed">
          <IconBellOff size={28} stroke={1.5} />
          <Text size="sm" mt="xs">
            {filter === 'unread'
              ? tr('Keine ungelesenen Benachrichtigungen.', 'No unread notifications.')
              : tr('Keine Benachrichtigungen.', 'No notifications.')}
          </Text>
        </Paper>
      ) : (
        <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
          {visible.map((n, i) => {
            const kind = KIND[n.kind] ?? KIND.info
            const link = safeNotificationLink(n.link) && n.club.slug
            return (
              <div
                key={`${n.club.slug ?? '-'}-${n.id}`}
                style={{
                  position: 'relative',
                  borderTop: i ? '1px solid var(--hb-border)' : undefined,
                  background: n.read
                    ? undefined
                    : 'color-mix(in srgb, var(--mantine-color-acc-6) 7%, transparent)',
                  boxShadow: n.read ? undefined : 'inset 3px 0 0 var(--mantine-color-acc-6)',
                }}
              >
                <UnstyledButton
                  onClick={() => open(n)}
                  style={{
                    display: 'flex',
                    gap: 12,
                    alignItems: 'flex-start',
                    width: '100%',
                    padding: '14px 52px 14px 16px',
                  }}
                >
                  <ThemeIcon variant="light" color={kind.color} radius="xl" size={30}>
                    {kind.icon}
                  </ThemeIcon>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text size="sm" fw={n.read ? 500 : 700} lineClamp={2}>
                      {show(notificationTitleText(n.title), n.title)}
                    </Text>
                    {n.msg && (
                      <Text size="xs" c="dimmed" lineClamp={3} mt={2}>
                        {show(notificationMessageText(n.msg), n.msg)}
                      </Text>
                    )}
                    <Group gap={6} mt={6}>
                      {clubs.size > 1 && n.club.name && (
                        <Badge size="xs" variant="light" color="gray">
                          {n.club.name}
                        </Badge>
                      )}
                      <Text size="xs" c="dimmed">
                        {when(n.time)}
                      </Text>
                      {link && (
                        <Text size="xs" c="acc.6" fw={600} style={{ display: 'flex', alignItems: 'center' }}>
                          {tr('Öffnen', 'Open')}
                          <IconChevronRight size={12} />
                        </Text>
                      )}
                    </Group>
                  </div>
                </UnstyledButton>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  size="sm"
                  onClick={() => remove(n)}
                  aria-label={tr('Löschen', 'Delete')}
                  style={{ position: 'absolute', top: 12, right: 12 }}
                >
                  <IconX size={14} />
                </ActionIcon>
              </div>
            )
          })}
        </Paper>
      )}

      <Modal
        opened={confirmClear}
        onClose={() => setConfirmClear(false)}
        title={tr('Alle Benachrichtigungen löschen?', 'Delete all notifications?')}
        size="sm"
        centered
      >
        <Text size="sm" c="dimmed">
          {tr(
            'Damit löschst du alle deine Benachrichtigungen in allen Vereinen, auch die ungelesenen. Andere Mitglieder sind nicht betroffen.',
            'This deletes all your notifications in all clubs, unread ones too. Other members keep theirs.',
          )}
        </Text>
        <Group justify="flex-end" mt="lg">
          <Button variant="default" onClick={() => setConfirmClear(false)}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            color="red"
            onClick={() => {
              clearAll()
              setConfirmClear(false)
            }}
          >
            {tr('Alle löschen', 'Delete all')}
          </Button>
        </Group>
      </Modal>
    </Stack>
  )
}
