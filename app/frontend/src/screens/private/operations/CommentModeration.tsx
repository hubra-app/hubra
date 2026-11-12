import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Anchor, Badge, Button, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { IconFlag } from '@tabler/icons-react'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDate } from '@/format'
import { useT } from '@/locales/i18n'
import {
  keepComment,
  listCommentMutes,
  listReportedComments,
  setCommentHidden,
  unmuteCommenter,
  type ReportedComment,
} from '@/api/posts'

/**
 * Above the posts, for moderators: comments members reported (hide or
 * keep them) and who is muted in comments until when. Shows nothing when
 * there is nothing to do.
 */
export function CommentModeration() {
  const { t } = useT()
  const { notify } = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState<string | null>(null)
  const reports = useQuery({ queryKey: qk.posts.reportedComments, queryFn: listReportedComments })
  const mutes = useQuery({ queryKey: qk.posts.commentMutes, queryFn: listCommentMutes })
  const open = reports.data?.items ?? []
  const muted = mutes.data?.items ?? []
  if (open.length === 0 && muted.length === 0) return null

  const act = async (key: string, action: () => Promise<unknown>, done: string, postId?: number) => {
    setBusy(key)
    try {
      await action()
      await queryClient.invalidateQueries({ queryKey: qk.posts.reportedComments })
      await queryClient.invalidateQueries({ queryKey: qk.posts.commentMutes })
      if (postId) void queryClient.invalidateQueries({ queryKey: qk.posts.comments(String(postId)) })
      notify('success', done)
    } catch (err) {
      notify('error', t('common.error', 'Fehler'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(null)
    }
  }

  const row = (r: ReportedComment) => {
    const post = String(r.post_id)
    const comment = String(r.comment_id)
    return (
      <Paper key={r.comment_id} withBorder p="sm" data-testid="reported-comment">
        <Group justify="space-between" align="flex-start" gap="sm" wrap="wrap">
          <Stack gap={4} style={{ flex: 1, minWidth: 220 }}>
            <Group gap={6}>
              <Text size="sm" fw={600}>
                {r.author_name}
              </Text>
              <Text size="xs" c="dimmed">
                {t('posts.moderation.onPost', 'zu')}{' '}
                <Anchor size="xs" onClick={() => navigate(`/app/operations/posts/${post}`)}>
                  {r.post_title}
                </Anchor>
              </Text>
              <Badge size="xs" color="orange" variant="light">
                {t('posts.moderation.reportedCount', '{{count}}× gemeldet', { count: r.reports })}
              </Badge>
            </Group>
            <Text size="sm" lineClamp={3}>
              {r.body}
            </Text>
            {r.reasons.length > 0 && (
              <Text size="xs" c="dimmed">
                {t('posts.moderation.reasons', 'Gründe: {{reasons}}', { reasons: r.reasons.join(' · ') })}
              </Text>
            )}
          </Stack>
          <Group gap="xs">
            <Button
              size="xs"
              variant="default"
              loading={busy === `keep-${comment}`}
              onClick={() =>
                void act(`keep-${comment}`, () => keepComment(post, comment), t('posts.moderation.kept', 'Kommentar bleibt'), r.post_id)
              }
            >
              {t('posts.moderation.keepShort', 'Behalten')}
            </Button>
            <Button
              size="xs"
              color="red"
              loading={busy === `hide-${comment}`}
              data-testid="reported-comment-hide"
              onClick={() =>
                void act(
                  `hide-${comment}`,
                  () => setCommentHidden(post, comment, true),
                  t('posts.moderation.hidden', 'Kommentar ausgeblendet'),
                  r.post_id,
                )
              }
            >
              {t('posts.moderation.hide', 'Ausblenden')}
            </Button>
          </Group>
        </Group>
      </Paper>
    )
  }

  return (
    <Paper withBorder p="md" mb={16} data-testid="comment-moderation">
      <Group gap={8} mb={8}>
        <IconFlag size={18} color="var(--mantine-color-orange-text)" />
        <Title order={4}>{t('posts.moderation.title', 'Moderation')}</Title>
      </Group>
      {open.length > 0 && (
        <Stack gap="xs" mb={muted.length ? 'md' : 0}>
          <Text size="sm" c="dimmed">
            {t('posts.moderation.openHint', 'Gemeldete Kommentare, die noch sichtbar sind.')}
          </Text>
          {open.map(row)}
        </Stack>
      )}
      {muted.length > 0 && (
        <Stack gap={6}>
          <Text size="sm" fw={600}>
            {t('posts.moderation.mutedTitle', 'Stummgeschaltet in Kommentaren')}
          </Text>
          {muted.map((m) => (
            <Group key={m.member_id} justify="space-between" gap="sm" wrap="nowrap">
              <Text size="sm">
                {m.member_name}{' '}
                <Text span size="xs" c="dimmed">
                  {t('posts.moderation.until', 'bis {{date}}', { date: formatDate(m.until) })}
                  {m.reason ? ` · ${m.reason}` : ''}
                </Text>
              </Text>
              <Button
                size="compact-xs"
                variant="subtle"
                loading={busy === `unmute-${m.member_id}`}
                onClick={() =>
                  void act(
                    `unmute-${m.member_id}`,
                    () => unmuteCommenter(m.member_id),
                    t('posts.moderation.unmuted', 'Stummschaltung aufgehoben'),
                  )
                }
              >
                {t('posts.moderation.unmute', 'Aufheben')}
              </Button>
            </Group>
          ))}
        </Stack>
      )}
    </Paper>
  )
}
