import { useState, useCallback } from 'react'
import {
  Group,
  Text,
  ActionIcon,
  Box,
  Menu,
  SegmentedControl,
  ThemeIcon,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  IconInfoCircle,
  IconAlertTriangle,
  IconCircleCheck,
  IconX,
  IconUsers,
  IconChecks,
  IconDots,
  IconTrash,
  IconBellOff,
  IconChevronRight,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav } from '@/context/AppContext'
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  deleteNotification,
  clearNotifications,
  type NotificationList,
} from '@/api/notifications'
import type { Notification } from '@/types'
import { qk } from '@/data/keys'
import { formatRelative } from '@/format'
import { SlideOver, ConfirmModal } from '@/components/feedback'
import { notificationMessage, notificationTitle, safeLink } from './notificationText'

const EMPTY: NotificationList = { items: [], unread: 0 }

const KIND: Record<Notification['kind'], { color: string; icon: React.ReactNode }> = {
  info: { color: 'blue', icon: <IconInfoCircle size={16} /> },
  success: { color: 'green', icon: <IconCircleCheck size={16} /> },
  warning: { color: 'yellow', icon: <IconAlertTriangle size={16} /> },
  member: { color: 'pink', icon: <IconUsers size={16} /> },
}

export function NotificationPanel() {
  const { t } = useT()
  const navigate = useNavigate()
  const { notifPanelOpen, setNotifPanelOpen } = useNav()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const [confirmClear, setConfirmClear] = useState(false)

  const { data = EMPTY } = useQuery<NotificationList>({
    queryKey: qk.notifications,
    queryFn: listNotifications,
    refetchInterval: 30_000,
  })
  const { items: notifications, unread } = data

  // Change the cached list at once, then the server; on failure show the
  // server's state again rather than a false one.
  const update = useCallback(
    (change: (prev: NotificationList) => NotificationList, request: Promise<void>) => {
      queryClient.setQueryData<NotificationList>(qk.notifications, (prev) =>
        change(prev ?? EMPTY),
      )
      request.catch(() => queryClient.invalidateQueries({ queryKey: qk.notifications }))
    },
    [queryClient],
  )

  const markAllRead = () =>
    update(
      (prev) => ({ items: prev.items.map((n) => ({ ...n, read: true })), unread: 0 }),
      markAllNotificationsRead(),
    )

  const remove = (n: Notification) =>
    update(
      (prev) => ({
        items: prev.items.filter((x) => x.id !== n.id),
        unread: Math.max(0, prev.unread - (n.read ? 0 : 1)),
      }),
      deleteNotification(n.id),
    )

  const clearRead = () =>
    update(
      (prev) => ({ items: prev.items.filter((x) => !x.read), unread: prev.unread }),
      clearNotifications(true),
    )

  const clearAll = () => update(() => EMPTY, clearNotifications())

  const open = (n: Notification) => {
    if (!n.read) {
      update(
        (prev) => ({
          items: prev.items.map((x) => (x.id === n.id ? { ...x, read: true } : x)),
          unread: Math.max(0, prev.unread - 1),
        }),
        markNotificationRead(n.id),
      )
    }
    const link = safeLink(n.link)
    if (link) {
      setNotifPanelOpen(false)
      navigate(link)
    }
  }

  const visible = filter === 'unread' ? notifications.filter((n) => !n.read) : notifications
  const hasRead = notifications.some((n) => n.read)

  return (
    <>
      <SlideOver
        opened={notifPanelOpen}
        onClose={() => setNotifPanelOpen(false)}
        width={400}
        padded={false}
        title={t('shell.notif.title', 'Benachrichtigungen')}
        subtitle={
          unread > 0
            ? t('shell.notif.unreadCount', '{{count}} ungelesen', { count: unread })
            : t('shell.notif.allRead', 'Alles gelesen')
        }
        actions={
          <>
            <Tooltip label={t('shell.notif.markAllRead', 'Alle als gelesen markieren')}>
              <ActionIcon
                variant="subtle"
                onClick={markAllRead}
                disabled={unread === 0}
                aria-label={t('shell.notif.markAllRead', 'Alle als gelesen markieren')}
              >
                <IconChecks size={18} />
              </ActionIcon>
            </Tooltip>
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  aria-label={t('shell.notif.more', 'Weitere Aktionen')}
                >
                  <IconDots size={18} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item
                  leftSection={<IconChecks size={16} />}
                  onClick={markAllRead}
                  disabled={unread === 0}
                >
                  {t('shell.notif.markAllRead', 'Alle als gelesen markieren')}
                </Menu.Item>
                <Menu.Item
                  leftSection={<IconTrash size={16} />}
                  onClick={clearRead}
                  disabled={!hasRead}
                >
                  {t('shell.notif.deleteRead', 'Gelesene löschen')}
                </Menu.Item>
                <Menu.Item
                  color="red"
                  leftSection={<IconTrash size={16} />}
                  onClick={() => setConfirmClear(true)}
                  disabled={notifications.length === 0}
                >
                  {t('shell.notif.deleteAll', 'Alle löschen')}
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </>
        }
      >
        <Box px="md" py="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
          <SegmentedControl
            fullWidth
            size="xs"
            value={filter}
            onChange={(v) => setFilter(v as 'all' | 'unread')}
            data={[
              { value: 'all', label: t('common.all', 'Alle') },
              {
                value: 'unread',
                label:
                  unread > 0
                    ? `${t('shell.notif.unread', 'Ungelesen')} (${unread > 99 ? '99+' : unread})`
                    : t('shell.notif.unread', 'Ungelesen'),
              },
            ]}
          />
        </Box>

        {visible.length === 0 ? (
          <Box ta="center" py={56} px="md" style={{ color: 'var(--hb-text-3)' }}>
            <IconBellOff size={28} stroke={1.5} />
            <Text fz="sm" mt="xs">
              {filter === 'unread'
                ? t('shell.notif.noUnread', 'Keine ungelesenen Benachrichtigungen.')
                : t('common.noNotifications', 'Keine Benachrichtigungen.')}
            </Text>
          </Box>
        ) : (
          visible.map((n) => {
            const link = safeLink(n.link)
            const kind = KIND[n.kind] ?? KIND.info
            return (
              <div
                key={n.id}
                className="hb-notif"
                data-unread={n.read ? undefined : ''}
                style={{ position: 'relative', borderBottom: '1px solid var(--hb-border)' }}
              >
                <UnstyledButton
                  onClick={() => open(n)}
                  style={{
                    display: 'flex',
                    gap: 12,
                    alignItems: 'flex-start',
                    width: '100%',
                    padding: '14px 52px 14px 20px',
                    cursor: link || !n.read ? 'pointer' : 'default',
                  }}
                >
                  <ThemeIcon variant="light" color={kind.color} radius="xl" size={30}>
                    {kind.icon}
                  </ThemeIcon>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text
                      fz="sm"
                      fw={n.read ? 500 : 700}
                      lineClamp={2}
                      style={{ color: 'var(--hb-text)' }}
                    >
                      {notificationTitle(n, t)}
                    </Text>
                    {n.msg && (
                      <Text fz="xs" lineClamp={3} mt={2} style={{ color: 'var(--hb-text-2)' }}>
                        {notificationMessage(n, t)}
                      </Text>
                    )}
                    <Group gap={4} mt={4} style={{ color: 'var(--hb-text-3)' }}>
                      <Text fz="xs">{formatRelative(n.time)}</Text>
                      {link && (
                        <>
                          <Text fz="xs">·</Text>
                          <Text fz="xs" c="acc.6" fw={600}>
                            {t('shell.notif.open', 'Öffnen')}
                          </Text>
                          <IconChevronRight size={12} color="var(--mantine-color-acc-6)" />
                        </>
                      )}
                    </Group>
                  </div>
                </UnstyledButton>
                <ActionIcon
                  className="hb-notif-delete"
                  variant="subtle"
                  color="gray"
                  size="sm"
                  onClick={() => remove(n)}
                  aria-label={t('shell.notif.delete', 'Löschen')}
                  style={{ position: 'absolute', top: 12, right: 16 }}
                >
                  <IconX size={14} />
                </ActionIcon>
              </div>
            )
          })
        )}
      </SlideOver>
      <ConfirmModal
        open={confirmClear}
        title={t('shell.notif.deleteAllTitle', 'Alle Benachrichtigungen löschen?')}
        body={t(
          'shell.notif.deleteAllBody',
          'Damit löschst du alle deine Benachrichtigungen, auch die ungelesenen. Andere Mitglieder sind nicht betroffen.',
        )}
        onConfirm={() => {
          clearAll()
          setConfirmClear(false)
        }}
        onClose={() => setConfirmClear(false)}
      />
    </>
  )
}
