import { useState, useCallback } from 'react'
import {
  Drawer,
  Group,
  Text,
  ActionIcon,
  Button,
  Box,
  Stack,
  SegmentedControl,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  IconInfoCircle,
  IconAlertTriangle,
  IconCircleCheck,
  IconX,
  IconUsers,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav } from '@/context/AppContext'
import {
  listNotifications,
  markAllNotificationsRead,
  deleteNotification,
} from '@/api/notifications'
import type { Notification } from '@/types'
import { qk } from '@/data/keys'
import { formatRelative } from '@/format'

export function NotificationPanel() {
  const { t } = useT()
  const { notifPanelOpen, setNotifPanelOpen } = useNav()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<'all' | 'unread'>('all')

  const { data: notifications = [] } = useQuery<Notification[]>({
    queryKey: qk.notifications,
    queryFn: listNotifications,
    refetchInterval: 30_000,
  })

  const markNotifsRead = useCallback(async () => {
    queryClient.setQueryData<Notification[]>(qk.notifications, (prev) =>
      (prev ?? []).map((n) => ({ ...n, read: true })),
    )
    try {
      await markAllNotificationsRead()
    } catch {
      // Show the server's state again rather than a false "all read".
      queryClient.invalidateQueries({ queryKey: qk.notifications })
    }
  }, [queryClient])

  const dismissNotif = useCallback(
    (id: string) => {
      queryClient.setQueryData<Notification[]>(qk.notifications, (prev) =>
        (prev ?? []).filter((n) => n.id !== id),
      )
      // Delete it on the server too, or the next refetch brings it back.
      deleteNotification(id).catch(() =>
        queryClient.invalidateQueries({ queryKey: qk.notifications }),
      )
    },
    [queryClient],
  )

  const icons: Record<string, React.ReactNode> = {
    info: <IconInfoCircle size={16} color="#2596be" />,
    success: <IconCircleCheck size={16} color="#1f9d57" />,
    warning: <IconAlertTriangle size={16} color="#c2870f" />,
    member: <IconUsers size={16} color="#fe64ac" />,
  }
  const visible =
    filter === 'unread' ? notifications.filter((n) => !n.read) : notifications

  return (
    <Drawer
      opened={notifPanelOpen}
      onClose={() => setNotifPanelOpen(false)}
      position="right"
      size={380}
      padding={0}
      withCloseButton={false}
      styles={{ content: { display: 'flex', flexDirection: 'column' } }}
    >
      <Group
        justify="space-between"
        px="lg"
        pt="lg"
        pb="sm"
        style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}
      >
        <Text fw={700} fz="md">
          {t('shell.notif.title')}
        </Text>
        <Group gap="xs">
          <Button variant="subtle" size="sm" onClick={markNotifsRead}>
            {t('shell.notif.markAllRead')}
          </Button>
          <ActionIcon
            variant="subtle"
            onClick={() => setNotifPanelOpen(false)}
            aria-label={t('common.close')}
          >
            <IconX size={16} />
          </ActionIcon>
        </Group>
      </Group>

      <Box
        px="md"
        py="xs"
        style={{ borderBottom: '1px solid var(--mantine-color-gray-2)' }}
      >
        <SegmentedControl
          size="xs"
          value={filter}
          onChange={(v) => setFilter(v as 'all' | 'unread')}
          data={[
            { value: 'all', label: t('common.all') },
            { value: 'unread', label: t('shell.notif.unread') },
          ]}
        />
      </Box>

      <Stack gap={0} style={{ flex: 1, overflowY: 'auto' }}>
        {visible.length === 0 ? (
          <Text c="dimmed" fz="sm" ta="center" py="xl">
            {filter === 'unread'
              ? t('shell.notif.noUnread')
              : t('common.noNotifications')}
          </Text>
        ) : (
          visible.map((n) => (
            <Group
              key={n.id}
              gap="md"
              p="md"
              style={{
                borderBottom: '1px solid var(--mantine-color-gray-2)',
                background: n.read ? 'transparent' : 'rgba(116,65,224,.06)',
              }}
              align="flex-start"
            >
              <Box style={{ flexShrink: 0, marginTop: 2 }}>{icons[n.kind]}</Box>
              <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
                <Text fz="sm" fw={600}>
                  {n.title}
                </Text>
                <Text fz="xs" c="dimmed">
                  {n.msg}
                </Text>
                <Text className="num" fz="xs" c="dimmed">
                  {formatRelative(n.time)}
                </Text>
              </Stack>
              <Group gap={6} align="flex-start" style={{ flexShrink: 0 }}>
                {!n.read && (
                  <Box
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: '#fece2b',
                      marginTop: 6,
                    }}
                  />
                )}
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  c="dimmed"
                  onClick={() => dismissNotif(n.id)}
                  aria-label={t('shell.tooltips.dismiss')}
                >
                  <IconX size={13} />
                </ActionIcon>
              </Group>
            </Group>
          ))
        )}
      </Stack>
    </Drawer>
  )
}
