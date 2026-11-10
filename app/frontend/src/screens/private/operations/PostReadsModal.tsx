import { useQuery } from '@tanstack/react-query'
import { Alert, Badge, Group, SimpleGrid, Stack, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { Modal, LoadingSpinner } from '@/components/ui'
import { qk } from '@/data/keys'
import { getReadStatus } from '@/api/posts'
import { formatDateTime } from '@/format'
import type { Post } from '@/types'

/** Must-read post: who confirmed it and who has not (for those who manage
 * the post). */
export function PostReadsModal({ post, onClose }: { post: Post | null; onClose: () => void }) {
  const { t } = useT()
  const { data, isLoading, isError } = useQuery({
    queryKey: qk.posts.reads(post?.id),
    queryFn: () => getReadStatus(post!.id),
    enabled: post !== null,
  })
  return (
    <Modal
      open={post !== null}
      onClose={onClose}
      title={t('posts.mustRead.statusTitle', 'Lesebestätigungen')}
      subtitle={post?.title}
    >
      {isLoading && <LoadingSpinner />}
      {isError && <Alert color="red">{t('posts.mustRead.statusFailed', 'Die Liste konnte nicht geladen werden.')}</Alert>}
      {data && (
        <>
          <Text size="sm" c="dimmed">
            {data.reminder_sent_at
              ? t('posts.mustRead.reminded', 'Erinnerung verschickt am {{when}}.', {
                  when: formatDateTime(data.reminder_sent_at),
                })
              : t(
                  'posts.mustRead.notReminded',
                  'Wer noch nicht bestätigt hat, bekommt nach der eingestellten Frist eine Erinnerung.',
                )}
          </Text>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
            <Stack gap={6} data-testid="reads-missing">
              <Group gap="xs">
                <Text fw={600} size="sm">
                  {t('posts.mustRead.missing', 'Noch nicht bestätigt')}
                </Text>
                <Badge color="orange" variant="light">
                  {data.missing.length}
                </Badge>
              </Group>
              {data.missing.map((m) => (
                <Text size="sm" key={m.member_id}>
                  {m.name}
                </Text>
              ))}
            </Stack>
            <Stack gap={6} data-testid="reads-confirmed">
              <Group gap="xs">
                <Text fw={600} size="sm">
                  {t('posts.mustRead.confirmed', 'Bestätigt')}
                </Text>
                <Badge color="green" variant="light">
                  {data.confirmed.length}
                </Badge>
              </Group>
              {data.confirmed.map((m) => (
                <Group gap="xs" key={m.member_id} justify="space-between" wrap="nowrap">
                  <Text size="sm">{m.name}</Text>
                  <Text size="xs" c="dimmed" className="num" style={{ whiteSpace: 'nowrap' }}>
                    {formatDateTime(m.read_at)}
                  </Text>
                </Group>
              ))}
            </Stack>
          </SimpleGrid>
        </>
      )}
    </Modal>
  )
}
