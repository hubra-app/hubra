import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  ThemeIcon,
  UnstyledButton,
} from '@mantine/core'
import {
  IconArrowBigUp,
  IconArrowBigUpFilled,
  IconBug,
  IconBulb,
  IconMessage,
} from '@tabler/icons-react'
import {
  EmptyState,
  LoadingSpinner,
  PageHead,
  PanelSection,
  SlideOver,
  Tabs,
} from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { formatDate, formatDateTime } from '@/format'
import { qk } from '@/data/keys'
import {
  myCase,
  myCases,
  replyToCase,
  roadmap,
  setVote,
  type CaseStatus,
  type RoadmapItem,
  type SupportCase,
} from '@/api/support'
import { openReport } from './reportStore'
import { STATUS_COLOR, deviceLines, statusLabel } from './labels'

type Tab = 'mine' | 'roadmap'

/** /app/feedback: the person's own reports and the roadmap to vote on. */
export function FeedbackScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const tab: Tab = location.pathname.endsWith('/roadmap') ? 'roadmap' : 'mine'

  return (
    <div>
      <PageHead
        title={t('support.page.title', 'Meldungen und Ideen')}
        desc={t(
          'support.page.desc',
          'Melde Probleme und schlage Ideen vor. Das Hubra-Team antwortet hier und per Mail.',
        )}
        actions={
          <Group gap="xs" wrap="wrap">
            <Button variant="default" leftSection={<IconBug size={16} />} onClick={() => openReport('bug')}>
              {t('support.menu.bug', 'Problem melden')}
            </Button>
            <Button leftSection={<IconBulb size={16} />} onClick={() => openReport('feature')}>
              {t('support.menu.feature', 'Idee vorschlagen')}
            </Button>
          </Group>
        }
      />
      <Tabs
        tabs={[
          { id: 'mine', label: t('support.page.tabMine', 'Meine Meldungen') },
          { id: 'roadmap', label: t('support.page.tabRoadmap', 'Roadmap') },
        ]}
        activeTab={tab}
        onTabChange={(id) => navigate(id === 'mine' ? '/app/feedback' : '/app/feedback/roadmap')}
      />
      {tab === 'mine' ? <MyCases /> : <Roadmap />}
    </div>
  )
}

function KindIcon({ kind }: { kind: SupportCase['kind'] }) {
  return (
    <ThemeIcon variant="light" radius="xl" size={34} color={kind === 'bug' ? 'red' : 'yellow'}>
      {kind === 'bug' ? <IconBug size={18} /> : <IconBulb size={18} />}
    </ThemeIcon>
  )
}

function StatusBadge({ status }: { status: CaseStatus }) {
  const { t } = useT()
  return (
    <Badge variant="light" color={STATUS_COLOR[status]} size="sm" style={{ flexShrink: 0 }}>
      {statusLabel(t, status)}
    </Badge>
  )
}

function MyCases() {
  const { t } = useT()
  const [openId, setOpenId] = useState<number | null>(null)
  const { data = [], isLoading } = useQuery({ queryKey: qk.support.mine, queryFn: myCases })

  if (isLoading) return <LoadingSpinner />
  if (data.length === 0)
    return (
      <EmptyState
        icon={<IconMessage size={26} stroke={1.6} />}
        title={t('support.page.noneTitle', 'Noch keine Meldungen')}
        description={t(
          'support.page.noneDesc',
          'Wenn etwas nicht klappt oder dir etwas fehlt: Das Hubra-Team liest jede Meldung.',
        )}
        action={{ label: t('support.menu.bug', 'Problem melden'), onClick: () => openReport('bug') }}
      />
    )

  return (
    <>
      <Stack gap={10} maw={860}>
        {data.map((c) => (
          <Paper
            key={c.id}
            withBorder
            radius="lg"
            p="md"
            component="button"
            type="button"
            onClick={() => setOpenId(c.id)}
            style={{ display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer', font: 'inherit', color: 'inherit' }}
          >
            <Group gap="sm" wrap="nowrap" align="flex-start">
              <KindIcon kind={c.kind} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <Group justify="space-between" wrap="nowrap" gap="xs" align="flex-start">
                  <Text fw={600} size="sm" style={{ wordBreak: 'break-word' }}>
                    {c.title}
                  </Text>
                  <StatusBadge status={c.status} />
                </Group>
                <Text size="xs" c="dimmed" mt={2}>
                  #{c.id} · {formatDate(c.createdAt)}
                  {c.commentCount > 0 &&
                    ` · ${t('support.page.answers', 'Antworten: {{count}}', { count: c.commentCount })}`}
                  {c.mergedInto &&
                    ` · ${t('support.page.mergedShort', 'zusammengeführt mit #{{id}}', { id: c.mergedInto.id })}`}
                </Text>
              </div>
            </Group>
          </Paper>
        ))}
      </Stack>
      {openId !== null && <CaseDetail id={openId} onClose={() => setOpenId(null)} />}
    </>
  )
}

function CaseDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)
  const { data: c } = useQuery({ queryKey: qk.support.case(id), queryFn: () => myCase(id) })

  const send = async () => {
    if (!reply.trim()) return
    setSending(true)
    try {
      await replyToCase(id, reply.trim())
      setReply('')
      await queryClient.invalidateQueries({ queryKey: qk.support.all })
    } catch (err) {
      notify('error', t('support.form.sendFailed', 'Senden fehlgeschlagen'), (err as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <SlideOver
      title={c ? c.title : '…'}
      subtitle={c ? `#${c.id} · ${formatDateTime(c.createdAt)}` : undefined}
      icon={c ? <KindIcon kind={c.kind} /> : undefined}
      width={520}
      padded={false}
      onClose={onClose}
      footer={
        c && !c.mergedInto ? (
          <Stack gap={8} w="100%">
            <Textarea
              value={reply}
              onChange={(e) => setReply(e.currentTarget.value)}
              placeholder={t('support.detail.replyPh', 'Antwort an das Hubra-Team …')}
              autosize
              minRows={2}
              maxRows={6}
              maxLength={5000}
            />
            <Group justify="flex-end">
              <Button onClick={() => void send()} loading={sending} disabled={!reply.trim()}>
                {t('support.detail.reply', 'Antworten')}
              </Button>
            </Group>
          </Stack>
        ) : undefined
      }
    >
      {!c ? (
        <LoadingSpinner />
      ) : (
        <>
          <PanelSection label={t('support.detail.status', 'Status')}>
            <Group gap="xs">
              <StatusBadge status={c.status} />
              {c.isPublic && (
                <Badge variant="outline" size="sm">
                  {t('support.detail.onRoadmap', 'Auf der Roadmap')}
                </Badge>
              )}
            </Group>
            {c.mergedInto && (
              <Text size="sm" mt={8}>
                {t(
                  'support.detail.merged',
                  'Zusammengeführt mit #{{id}} «{{title}}»: dort geht es weiter ({{status}}).',
                  { id: c.mergedInto.id, title: c.mergedInto.title, status: statusLabel(t, c.mergedInto.status) },
                )}
              </Text>
            )}
          </PanelSection>
          <PanelSection label={c.kind === 'bug' ? t('support.form.whatHappened', 'Was ist passiert?') : t('support.form.idea', 'Was wünschst du dir?')}>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {c.description}
            </Text>
          </PanelSection>
          {c.steps && (
            <PanelSection label={t('support.form.steps', 'Wie kommt man dahin?')}>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                {c.steps}
              </Text>
            </PanelSection>
          )}
          {c.expected && (
            <PanelSection label={t('support.form.expected', 'Was hättest du erwartet?')}>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                {c.expected}
              </Text>
            </PanelSection>
          )}
          {c.useCase && (
            <PanelSection label={t('support.form.useCase', 'Wofür brauchst du das?')}>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                {c.useCase}
              </Text>
            </PanelSection>
          )}
          <PanelSection label={t('support.detail.conversation', 'Verlauf')}>
            {(c.comments ?? []).length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('support.detail.noAnswers', 'Noch keine Antwort. Du bekommst eine Mail, sobald sich etwas tut.')}
              </Text>
            ) : (
              <Stack gap={10}>
                {(c.comments ?? []).map((m) => (
                  <Paper
                    key={m.id}
                    radius="md"
                    p="sm"
                    bg={m.fromStaff ? 'var(--mantine-color-acc-light)' : 'var(--hb-surface-2, var(--mantine-color-gray-0))'}
                    ml={m.fromStaff ? 0 : 24}
                    mr={m.fromStaff ? 24 : 0}
                  >
                    <Text size="xs" fw={600} c="dimmed" mb={2}>
                      {m.fromStaff ? t('support.detail.team', 'Hubra-Team') : t('support.detail.you', 'Du')} ·{' '}
                      {formatDateTime(m.createdAt)}
                    </Text>
                    <Text size="sm" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {m.body}
                    </Text>
                  </Paper>
                ))}
              </Stack>
            )}
          </PanelSection>
          <PanelSection border={false} label={t('support.detail.device', 'Mitgeschickt')}>
            <Stack gap={2}>
              {deviceLines(c.fingerprint, t, c.page).map(([label, value]) => (
                <Text key={label} size="xs">
                  <Text span size="xs" c="dimmed">
                    {label}:
                  </Text>{' '}
                  {value}
                </Text>
              ))}
            </Stack>
          </PanelSection>
        </>
      )}
    </SlideOver>
  )
}

const COLUMNS: { status: CaseStatus; key: string; fallback: string }[] = [
  { status: 'in_progress', key: 'support.roadmap.inProgress', fallback: 'In Arbeit' },
  { status: 'planned', key: 'support.roadmap.planned', fallback: 'Geplant' },
  { status: 'open', key: 'support.roadmap.open', fallback: 'Vorgeschlagen' },
  { status: 'done', key: 'support.roadmap.done', fallback: 'Erledigt' },
]

function Roadmap() {
  const { t } = useT()
  const { data = [], isLoading } = useQuery({ queryKey: qk.support.roadmap, queryFn: roadmap })

  if (isLoading) return <LoadingSpinner />
  if (data.length === 0)
    return (
      <EmptyState
        icon={<IconBulb size={26} stroke={1.6} />}
        title={t('support.roadmap.emptyTitle', 'Die Roadmap ist noch leer')}
        description={t(
          'support.roadmap.emptyDesc',
          'Hier erscheinen Ideen, die das Hubra-Team öffentlich gemacht hat. Stimme für die Ideen, die dir am meisten helfen.',
        )}
        action={{ label: t('support.menu.feature', 'Idee vorschlagen'), onClick: () => openReport('feature') }}
      />
    )

  return (
    <Stack gap={12}>
      <Text size="sm" c="dimmed" maw={720}>
        {t(
          'support.roadmap.intro',
          'Ideen, an denen das Hubra-Team arbeitet oder die es prüft. Deine Stimme hilft beim Entscheiden, was zuerst kommt.',
        )}
      </Text>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        {COLUMNS.map((col) => {
          const items = data.filter((i) => i.status === col.status)
          return (
            <Stack key={col.status} gap={8}>
              <Group gap={6}>
                <Badge variant="light" color={STATUS_COLOR[col.status]}>
                  {t(col.key, col.fallback)}
                </Badge>
                <Text size="xs" c="dimmed">
                  {items.length}
                </Text>
              </Group>
              {items.length === 0 ? (
                <Text size="xs" c="dimmed">
                  {t('support.roadmap.none', 'Nichts hier.')}
                </Text>
              ) : (
                items.map((item) => <RoadmapCard key={item.id} item={item} />)
              )}
            </Stack>
          )
        })}
      </SimpleGrid>
    </Stack>
  )
}

function RoadmapCard({ item }: { item: RoadmapItem }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const done = item.status === 'done'

  const toggle = async () => {
    setBusy(true)
    try {
      const res = await setVote(item.id, !item.voted)
      queryClient.setQueryData<RoadmapItem[]>(qk.support.roadmap, (old) =>
        old?.map((i) => (i.id === item.id ? { ...i, votes: res.votes, voted: res.voted } : i)),
      )
    } catch (err) {
      notify('error', t('support.roadmap.voteFailed', 'Abstimmen fehlgeschlagen'), (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder radius="lg" p="sm">
      <Group gap="sm" wrap="nowrap" align="flex-start">
        <UnstyledButton
          onClick={() => void toggle()}
          disabled={busy || done}
          aria-pressed={!!item.voted}
          aria-label={item.voted ? t('support.roadmap.unvote', 'Stimme zurücknehmen') : t('support.roadmap.vote', 'Dafür stimmen')}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            minWidth: 44,
            padding: '6px 4px',
            borderRadius: 10,
            border: '1px solid var(--hb-border)',
            color: item.voted ? 'var(--mantine-color-acc-6)' : 'var(--hb-text-2)',
            background: item.voted ? 'var(--mantine-color-acc-light)' : 'transparent',
            cursor: done ? 'default' : 'pointer',
          }}
        >
          {item.voted ? <IconArrowBigUpFilled size={18} /> : <IconArrowBigUp size={18} />}
          <Text size="sm" fw={700}>
            {item.votes}
          </Text>
        </UnstyledButton>
        <div style={{ minWidth: 0 }}>
          <Text fw={600} size="sm" style={{ wordBreak: 'break-word' }}>
            {item.title}
          </Text>
          <Text size="xs" c="dimmed" lineClamp={4} style={{ whiteSpace: 'pre-wrap' }}>
            {item.description}
          </Text>
        </div>
      </Group>
    </Paper>
  )
}
