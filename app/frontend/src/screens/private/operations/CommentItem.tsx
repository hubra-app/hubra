import { useState } from 'react'
import { ActionIcon, Badge, Button, Group, Menu, Modal, Select, Stack, Text, Textarea } from '@mantine/core'
import { IconDots, IconEye, IconEyeOff, IconFlag, IconCheck, IconMicrophoneOff, IconTrash } from '@tabler/icons-react'
import { useQueryClient } from '@tanstack/react-query'
import { Avatar } from '@/components/ui'
import { useAuth, useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useT } from '@/locales/i18n'
import { keepComment, muteCommenter, reportComment, setCommentHidden } from '@/api/posts'
import type { PostComment } from '@/types'

const MUTE_DAYS = ['1', '3', '7', '14', '30']

/**
 * One comment under a post, with its menu: report it, and for moderators
 * hide or show it, keep a reported one, or mute its author in comments
 * for some days (hubra/api/posts/moderation.py). The backend sends the
 * report count only to those who may moderate the post.
 */
export function CommentItem({
  postId,
  comment,
  canDelete,
  onDelete,
  onChange,
}: {
  postId: string
  comment: PostComment
  canDelete: boolean
  onDelete: () => void
  onChange: (updated: PostComment) => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser, hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [dialog, setDialog] = useState<'report' | 'mute' | null>(null)
  const [reason, setReason] = useState('')
  const [days, setDays] = useState('7')
  const [busy, setBusy] = useState(false)

  const own = comment.authorId === currentUser?.id
  const moderator = comment.reports !== undefined
  const canMute = hasPermission('posts.posts.moderate') && !own
  const reported = comment.reports ?? 0

  const run = async (action: () => Promise<PostComment | unknown>, done: string) => {
    setBusy(true)
    try {
      const result = await action()
      if (result && typeof result === 'object' && 'authorId' in result) onChange(result as PostComment)
      void queryClient.invalidateQueries({ queryKey: qk.posts.reportedComments })
      void queryClient.invalidateQueries({ queryKey: qk.posts.commentMutes })
      notify('success', done)
      setDialog(null)
      setReason('')
    } catch (err) {
      notify('error', t('common.error', 'Fehler'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  const items = [
    !own && !comment.reportedByMe && (
      <Menu.Item key="report" leftSection={<IconFlag size={14} />} onClick={() => setDialog('report')}>
        {t('posts.moderation.report', 'Melden')}
      </Menu.Item>
    ),
    moderator && (
      <Menu.Item
        key="hide"
        leftSection={comment.hidden ? <IconEye size={14} /> : <IconEyeOff size={14} />}
        onClick={() =>
          void run(
            () => setCommentHidden(postId, comment.id, !comment.hidden),
            comment.hidden
              ? t('posts.moderation.shown', 'Kommentar wieder eingeblendet')
              : t('posts.moderation.hidden', 'Kommentar ausgeblendet'),
          )
        }
      >
        {comment.hidden ? t('posts.moderation.show', 'Einblenden') : t('posts.moderation.hide', 'Ausblenden')}
      </Menu.Item>
    ),
    moderator && reported > 0 && !comment.hidden && (
      <Menu.Item
        key="keep"
        leftSection={<IconCheck size={14} />}
        onClick={() => void run(() => keepComment(postId, comment.id), t('posts.moderation.kept', 'Kommentar bleibt'))}
      >
        {t('posts.moderation.keep', 'Behalten (Meldungen erledigt)')}
      </Menu.Item>
    ),
    canMute && (
      <Menu.Item key="mute" leftSection={<IconMicrophoneOff size={14} />} onClick={() => setDialog('mute')}>
        {t('posts.moderation.mute', 'Beim Kommentieren stummschalten …')}
      </Menu.Item>
    ),
    canDelete && (
      <Menu.Item key="delete" color="red" leftSection={<IconTrash size={14} />} onClick={onDelete}>
        {t('common.delete', 'Löschen')}
      </Menu.Item>
    ),
  ].filter(Boolean)

  return (
    <div style={{ display: 'flex', gap: 8 }} data-testid="comment" data-hidden={comment.hidden ? 'true' : undefined}>
      <Avatar name={comment.author} color={comment.avatarColor} size={28} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <Group gap={6} mb={2} wrap="nowrap">
          <Text fz="xs" fw={600} c="var(--hb-text)">
            {comment.author}
          </Text>
          <Text className="num" fz="xs" c="var(--hb-text-3)">
            {comment.time}
          </Text>
          {moderator && comment.hidden && (
            <Badge size="xs" variant="light" color="gray">
              {t('posts.moderation.hiddenBadge', 'Ausgeblendet')}
            </Badge>
          )}
          {reported > 0 && !comment.hidden && (
            <Badge size="xs" variant="light" color="orange">
              {t('posts.moderation.reportedCount', '{{count}}× gemeldet', { count: reported })}
            </Badge>
          )}
          {comment.reportedByMe && !moderator && (
            <Badge size="xs" variant="light" color="gray">
              {t('posts.moderation.reportedByMe', 'Gemeldet')}
            </Badge>
          )}
          {items.length > 0 && (
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  ml="auto"
                  aria-label={t('posts.moderation.menu', 'Aktionen zum Kommentar')}
                  data-testid="comment-menu"
                >
                  <IconDots size={14} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>{items}</Menu.Dropdown>
            </Menu>
          )}
        </Group>
        {comment.hidden && !moderator ? (
          <Text fz="sm" fs="italic" c="var(--hb-text-3)">
            {t('posts.moderation.hiddenText', 'Von der Moderation ausgeblendet.')}
          </Text>
        ) : (
          <Text fz="sm" c={comment.hidden ? 'var(--hb-text-3)' : 'var(--hb-text)'} lh={1.5}>
            {comment.body}
          </Text>
        )}
      </div>

      <Modal
        opened={dialog === 'report'}
        onClose={() => setDialog(null)}
        title={t('posts.moderation.reportTitle', 'Kommentar melden')}
        size="sm"
      >
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {t(
              'posts.moderation.reportHint',
              'Die Moderation sieht deine Meldung und entscheidet, ob der Kommentar ausgeblendet wird. Wer gemeldet hat, sieht nur die Moderation.',
            )}
          </Text>
          <Textarea
            label={t('posts.moderation.reason', 'Grund (freiwillig)')}
            value={reason}
            maxLength={300}
            autosize
            minRows={2}
            onChange={(e) => setReason(e.currentTarget.value)}
          />
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setDialog(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button
              loading={busy}
              data-testid="comment-report-send"
              onClick={() =>
                void run(
                  () => reportComment(postId, comment.id, reason),
                  t('posts.moderation.reported', 'Gemeldet. Danke!'),
                )
              }
            >
              {t('posts.moderation.report', 'Melden')}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={dialog === 'mute'}
        onClose={() => setDialog(null)}
        title={t('posts.moderation.muteTitle', '{{name}} stummschalten', { name: comment.author })}
        size="sm"
      >
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {t(
              'posts.moderation.muteHint',
              'Während dieser Zeit kann {{name}} Beiträge lesen, aber nicht kommentieren. Das Audit-Log hält fest, wer stummgeschaltet hat.',
              { name: comment.author },
            )}
          </Text>
          <Select
            label={t('posts.moderation.muteFor', 'Dauer')}
            data={MUTE_DAYS.map((d) => ({
              value: d,
              label: t('posts.moderation.days', '{{count}} Tage', { count: Number(d) }),
            }))}
            value={days}
            onChange={(v) => setDays(v ?? '7')}
            allowDeselect={false}
          />
          <Textarea
            label={t('posts.moderation.reason', 'Grund (freiwillig)')}
            value={reason}
            maxLength={300}
            autosize
            minRows={2}
            onChange={(e) => setReason(e.currentTarget.value)}
          />
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => setDialog(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button
              loading={busy}
              color="red"
              onClick={() =>
                void run(
                  () => muteCommenter(comment.authorId, Number(days), reason),
                  t('posts.moderation.muted', 'Stummgeschaltet'),
                )
              }
            >
              {t('posts.moderation.muteConfirm', 'Stummschalten')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </div>
  )
}
