import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Center,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Textarea,
} from '@mantine/core'
import { IconArrowLeft, IconBug, IconBulb, IconMessage, IconMessageCircle } from '@tabler/icons-react'
import { EmptyState } from '@hubra/ui'
import { Page } from '@/components/Layout'
import { SignInNeeded } from '@/components/SignInNeeded'
import { useAuth } from '@/auth'
import { getLang, useLang } from '@/lang'
import { myCase, myCases, replyToCase, type CaseKind, type SupportCase } from '@/api/support'
import { KIND_COLOR, STATUS_COLOR, areaLabel, kindLabel, statusLabel } from '@/lib/labels'

function date(iso: string) {
  return new Date(iso).toLocaleString(getLang() === 'en' ? 'en-GB' : 'de-CH', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const KIND_ICON: Record<CaseKind, typeof IconBug> = {
  bug: IconBug,
  feature: IconBulb,
  question: IconMessageCircle,
}

function CaseBadges({ c }: { c: SupportCase }) {
  const { tr } = useLang()
  return (
    <Group gap={6}>
      <Badge variant="light" color={KIND_COLOR[c.kind]} size="sm">
        {kindLabel(tr, c.kind)}
      </Badge>
      <Badge variant="light" color={STATUS_COLOR[c.status]} size="sm">
        {statusLabel(tr, c.status)}
      </Badge>
      {c.isPublic && (
        <Badge variant="outline" color="violet" size="sm">
          {tr('Auf der Roadmap', 'On the roadmap')}
        </Badge>
      )}
    </Group>
  )
}

/** /meine: the person's own problem reports, ideas and questions. */
export function MyCasesScreen() {
  const { tr } = useLang()
  const { status } = useAuth()
  const query = useQuery({ queryKey: ['my-cases'], queryFn: myCases, enabled: status === 'authed' })
  return (
    <Page
      narrow
      title={tr('Meine Meldungen', 'My reports')}
      intro={tr(
        'Was du gemeldet, vorgeschlagen oder gefragt hast, und was das Hubra-Team dazu schreibt.',
        'What you reported, suggested or asked, and what the Hubra team writes about it.',
      )}
      actions={
        status === 'authed' ? (
          <Group gap="xs">
            <Button component={Link} to="/melden" variant="light" size="sm">
              {tr('Problem melden', 'Report a problem')}
            </Button>
            <Button component={Link} to="/idee" variant="default" size="sm">
              {tr('Idee', 'Idea')}
            </Button>
          </Group>
        ) : undefined
      }
    >
      {status !== 'authed' ? (
        <SignInNeeded why={tr('Deine Meldungen sind nur für dich sichtbar.', 'Your reports are visible only to you.')} />
      ) : query.isLoading ? (
        <Center py={60}>
          <Loader />
        </Center>
      ) : query.isError ? (
        <Text c="red">{(query.error as Error).message}</Text>
      ) : !query.data?.length ? (
        <EmptyState
          icon={<IconMessage size={28} />}
          title={tr('Noch nichts gemeldet', 'Nothing reported yet')}
          description={tr(
            'Wenn du ein Problem meldest oder eine Idee schickst, steht sie hier.',
            'When you report a problem or send an idea, it shows up here.',
          )}
        />
      ) : (
        <Stack gap="sm">
          {query.data.map((c) => {
            const Icon = KIND_ICON[c.kind]
            return (
              <Paper key={c.id} component={Link} to={`/meine/${c.id}`} withBorder radius="lg" p="md" className="sp-tile">
                <Group wrap="nowrap" align="flex-start" gap="md">
                  <Box pt={2} c={`${KIND_COLOR[c.kind]}.6`}>
                    <Icon size={20} />
                  </Box>
                  <Box style={{ flex: 1, minWidth: 0 }}>
                    <Group justify="space-between" gap="xs" wrap="wrap">
                      <Text fw={650} style={{ overflowWrap: 'anywhere' }}>
                        #{c.id} {c.title}
                      </Text>
                      <CaseBadges c={c} />
                    </Group>
                    <Text size="sm" c="dimmed" mt={4}>
                      {date(c.createdAt)}
                      {c.commentCount
                        ? ` · ${tr(`${c.commentCount} Antwort${c.commentCount === 1 ? '' : 'en'}`, `${c.commentCount} repl${c.commentCount === 1 ? 'y' : 'ies'}`)}`
                        : ''}
                      {c.kind === 'feature' && c.isPublic ? ` · ${tr(`${c.votes} Stimmen`, `${c.votes} votes`)}` : ''}
                    </Text>
                  </Box>
                </Group>
              </Paper>
            )
          })}
        </Stack>
      )}
    </Page>
  )
}

/** /meine/:id: one case with the answers, and a reply box. */
export function CaseScreen() {
  const { tr } = useLang()
  const { status, notify } = useAuth()
  const { id } = useParams()
  const caseId = Number(id)
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['my-case', caseId],
    queryFn: () => myCase(caseId),
    enabled: status === 'authed' && Number.isFinite(caseId),
  })
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)
  const c = query.data

  const send = async () => {
    if (!reply.trim()) return
    setSending(true)
    try {
      await replyToCase(caseId, reply.trim())
      setReply('')
      await queryClient.invalidateQueries({ queryKey: ['my-case', caseId] })
    } catch (err) {
      notify('error', tr('Senden fehlgeschlagen', 'Sending failed'), (err as Error).message)
    } finally {
      setSending(false)
    }
  }

  const back = (
    <Anchor component={Link} to="/meine" size="sm" mb="md" display="inline-flex" style={{ alignItems: 'center', gap: 4 }}>
      <IconArrowLeft size={14} /> {tr('Meine Meldungen', 'My reports')}
    </Anchor>
  )

  if (status !== 'authed')
    return (
      <Page narrow title={tr('Meldung', 'Report')}>
        <SignInNeeded why={tr('Deine Meldungen sind nur für dich sichtbar.', 'Your reports are visible only to you.')} />
      </Page>
    )
  if (query.isLoading)
    return (
      <Center py={80}>
        <Loader />
      </Center>
    )
  if (!c)
    return (
      <Page narrow title={tr('Meldung nicht gefunden', 'Report not found')}>
        {back}
        <Text c="dimmed">{tr('Diese Meldung gibt es nicht, oder sie ist nicht von dir.', 'This report does not exist, or it is not yours.')}</Text>
      </Page>
    )

  const finished = c.status === 'done' || c.status === 'closed'
  return (
    <Page narrow title={`#${c.id} ${c.title}`}>
      <Box mt={-12} mb="md">
        {back}
        <CaseBadges c={c} />
        <Text size="sm" c="dimmed" mt={6}>
          {tr('Gesendet', 'Sent')} {date(c.createdAt)}
          {c.area ? ` · ${areaLabel(tr, c.area)}` : ''}
        </Text>
      </Box>
      {c.mergedInto && (
        <Alert color="violet" variant="light" mb="md">
          {tr('Zusammengelegt mit', 'Merged into')} #{c.mergedInto.id} {c.mergedInto.title} ({statusLabel(tr, c.mergedInto.status)})
        </Alert>
      )}
      <Paper withBorder radius="lg" p="md">
        <Stack gap="sm">
          <Box>
            <Text size="xs" fw={700} c="dimmed" tt="uppercase">
              {c.kind === 'bug' ? tr('Was ist passiert?', 'What happened?') : c.kind === 'feature' ? tr('Die Idee', 'The idea') : tr('Frage', 'Question')}
            </Text>
            <Text style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{c.description}</Text>
          </Box>
          {c.steps && (
            <Box>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase">
                {tr('Schritte', 'Steps')}
              </Text>
              <Text style={{ whiteSpace: 'pre-wrap' }}>{c.steps}</Text>
            </Box>
          )}
          {c.expected && (
            <Box>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase">
                {tr('Erwartet', 'Expected')}
              </Text>
              <Text style={{ whiteSpace: 'pre-wrap' }}>{c.expected}</Text>
            </Box>
          )}
          {c.useCase && (
            <Box>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase">
                {tr('Wofür', 'What for')}
              </Text>
              <Text style={{ whiteSpace: 'pre-wrap' }}>{c.useCase}</Text>
            </Box>
          )}
        </Stack>
      </Paper>

      <Text fw={700} mt="xl" mb="sm">
        {tr('Verlauf', 'Conversation')}
      </Text>
      <Stack gap="sm">
        {(c.comments ?? []).length === 0 && (
          <Text size="sm" c="dimmed">
            {tr('Noch keine Antwort. Du bekommst eine Mail, sobald das Hubra-Team schreibt.', 'No answer yet. You get a mail as soon as the Hubra team writes.')}
          </Text>
        )}
        {(c.comments ?? []).map((m) => (
          <Paper
            key={m.id}
            withBorder
            radius="lg"
            p="sm"
            bg={m.fromStaff ? 'var(--mantine-color-acc-light)' : undefined}
            ml={m.fromStaff ? 0 : { base: 16, sm: 48 }}
            mr={m.fromStaff ? { base: 16, sm: 48 } : 0}
          >
            <Text size="xs" fw={700} c="dimmed">
              {m.fromStaff ? tr('Hubra-Team', 'Hubra team') : (m.author ?? tr('Du', 'You'))} · {date(m.createdAt)}
            </Text>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {m.body}
            </Text>
          </Paper>
        ))}
      </Stack>
      {!finished && !c.mergedInto && (
        <Paper withBorder radius="lg" p="md" mt="md">
          <Textarea
            label={tr('Antworten', 'Reply')}
            value={reply}
            onChange={(e) => setReply(e.currentTarget.value)}
            autosize
            minRows={3}
            maxRows={10}
            maxLength={5000}
          />
          <Group justify="flex-end" mt="sm">
            <Button onClick={() => void send()} loading={sending} disabled={!reply.trim()}>
              {tr('Senden', 'Send')}
            </Button>
          </Group>
        </Paper>
      )}
    </Page>
  )
}
