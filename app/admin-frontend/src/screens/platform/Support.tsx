import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Anchor,
  Badge,
  Button,
  Checkbox,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import {
  IconArrowBigUp,
  IconArrowLeft,
  IconBrandDiscord,
  IconBug,
  IconBulb,
  IconGitMerge,
  IconLock,
  IconMessageCircle,
  IconMessageQuestion,
  IconPencil,
  IconSearch,
  IconUserPlus,
  IconX,
} from '@tabler/icons-react'
import { EmptyState, PageHead, Pagination, Tabs } from '@/components/ui'
import { useAdmin } from '@/context/AdminContext'
import { formatDate, formatDateTime } from '@/format'
import { getLang, tr } from '@/lang'
import { getRoadmap } from '@/api/platform'
import {
  addPeople,
  commentOnCase,
  findAccounts,
  getCase,
  openThread,
  removePerson,
  listCases,
  mergeCase,
  updateCase,
  type Account,
  type CaseKind,
  type CasePerson,
  type CaseStatus,
  type DiscordState,
  type Fingerprint,
  type StaffCase,
} from '@/api/support'

const STATUSES: CaseStatus[] = ['open', 'planned', 'in_progress', 'done', 'closed']

const STATUS_COLOR: Record<CaseStatus, string> = {
  open: 'gray',
  planned: 'acc',
  in_progress: 'orange',
  done: 'green',
  closed: 'gray',
}

function statusLabel(s: CaseStatus) {
  return {
    open: tr('Offen', 'Open'),
    planned: tr('Geplant', 'Planned'),
    in_progress: tr('In Arbeit', 'In progress'),
    done: tr('Erledigt', 'Done'),
    closed: tr('Geschlossen', 'Closed'),
  }[s]
}

function severityLabel(s: StaffCase['severity']) {
  if (!s) return null
  return {
    minor: tr('Kleinigkeit', 'Minor'),
    annoying: tr('Stört bei der Arbeit', 'Gets in the way'),
    blocking: tr('Kommt nicht weiter', 'Blocked'),
  }[s]
}

const pickTitle = (t: Record<string, string>) => t[getLang()] ?? t.en ?? t.de ?? Object.values(t)[0] ?? ''

const AREAS = [
  'modules',
  'members',
  'finance',
  'events',
  'posts',
  'polls',
  'groups',
  'inventory',
  'mail',
  'settings',
  'account',
  'other',
] as const

function areaLabel(a: string | null) {
  if (!a) return null
  const labels: Record<string, [string, string]> = {
    members: ['Mitglieder', 'Members'],
    finance: ['Finanzen', 'Finances'],
    events: ['Anlässe', 'Events'],
    posts: ['Beiträge', 'Posts'],
    polls: ['Umfragen', 'Polls'],
    groups: ['Gruppen', 'Groups'],
    inventory: ['Inventar', 'Inventory'],
    mail: ['Mail', 'Mail'],
    settings: ['Einstellungen', 'Settings'],
    account: ['Konto und Anmeldung', 'Account and sign-in'],
    modules: ['Modul', 'Module'],
    other: ['Anderes', 'Other'],
  }
  const l = labels[a]
  return l ? tr(l[0], l[1]) : a
}

function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <Badge variant="light" color={STATUS_COLOR[status]} size="sm" style={{ flexShrink: 0 }}>
      {statusLabel(status)}
    </Badge>
  )
}

const KIND_COLOR: Record<CaseKind, string> = { bug: 'red', feature: 'orange', question: 'blue' }

function kindLabel(kind: CaseKind): string {
  return kind === 'bug' ? tr('Problem', 'Problem') : kind === 'feature' ? tr('Idee', 'Idea') : tr('Frage', 'Question')
}

function KindIcon({ kind, size = 34 }: { kind: CaseKind; size?: number }) {
  const Icon = kind === 'bug' ? IconBug : kind === 'feature' ? IconBulb : IconMessageQuestion
  return (
    <ThemeIcon variant="light" radius="xl" size={size} color={KIND_COLOR[kind]}>
      <Icon size={size / 2} />
    </ThemeIcon>
  )
}

function deviceText(fp: Fingerprint): string {
  const parts = [
    [fp.browser, fp.browserVersion].filter(Boolean).join(' '),
    [fp.os, fp.osVersion].filter(Boolean).join(' '),
  ].filter(Boolean)
  return parts.join(' · ')
}

type KindTab = 'bug' | 'feature' | 'question' | 'all'

/** manage › Support: problem reports, feature requests and questions from
 * the app and the support site (support.hubra.club). */
export function SupportCases() {
  const { id } = useParams()
  return id ? <CaseDetail id={Number(id)} /> : <CaseList />
}

function CaseList() {
  const navigate = useNavigate()
  const [kind, setKind] = useState<KindTab>('bug')
  const [status, setStatus] = useState<CaseStatus | 'active' | ''>('active')
  const [area, setArea] = useState('')
  const [search, setSearch] = useState('')
  const [q] = useDebouncedValue(search.trim(), 250)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)

  const query = useQuery({
    queryKey: ['support-cases', kind, status, area, q, page, perPage],
    queryFn: () =>
      listCases({ kind: kind === 'all' ? '' : kind, status, area, q, page, perPage }),
    placeholderData: (prev) => prev,
  })
  const data = query.data
  const counts = data?.openCounts ?? { bug: 0, feature: 0, question: 0 }
  const items = data?.items ?? []

  return (
    <div>
      <PageHead
        title={tr('Meldungen & Ideen', 'Reports & ideas')}
        desc={tr(
          'Problemmeldungen, Ideen und Fragen aus der App und von der Support-Seite. Antworten gehen per Mail an die meldende Person; interne Notizen sieht nur das Team.',
          'Problem reports, ideas and questions from the app and the support site. Answers are mailed to the reporter; internal notes stay with the team.',
        )}
      />
      <Tabs
        tabs={[
          { id: 'bug', label: `${tr('Probleme', 'Problems')} (${counts.bug})`, icon: <IconBug size={16} /> },
          { id: 'feature', label: `${tr('Ideen', 'Ideas')} (${counts.feature})`, icon: <IconBulb size={16} /> },
          {
            id: 'question',
            label: `${tr('Fragen', 'Questions')} (${counts.question ?? 0})`,
            icon: <IconMessageQuestion size={16} />,
          },
          { id: 'all', label: tr('Alle', 'All') },
        ]}
        activeTab={kind}
        onTabChange={(v) => {
          setKind(v as KindTab)
          setPage(1)
        }}
      />
      <Group gap={10} mb={14} wrap="wrap">
        <TextInput
          leftSection={<IconSearch size={16} />}
          placeholder={tr('Titel, Text oder #Nummer …', 'Title, text or #number…')}
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value)
            setPage(1)
          }}
          style={{ flex: 1, minWidth: 200 }}
        />
        <Select
          value={status}
          onChange={(v) => {
            setStatus((v ?? '') as CaseStatus | 'active' | '')
            setPage(1)
          }}
          allowDeselect={false}
          w={200}
          data={[
            { value: 'active', label: tr('Offen und in Arbeit', 'Open and in progress') },
            ...STATUSES.map((s) => ({ value: s, label: statusLabel(s) })),
            { value: '', label: tr('Alle Status', 'Any status') },
          ]}
        />
        <Select
          value={area}
          onChange={(v) => {
            setArea(v ?? '')
            setPage(1)
          }}
          allowDeselect={false}
          w={200}
          aria-label={tr('Bereich', 'Area')}
          data={[
            { value: '', label: tr('Alle Bereiche', 'Any area') },
            ...AREAS.map((a) => ({ value: a, label: areaLabel(a) ?? a })),
          ]}
        />
      </Group>

      {query.isLoading ? (
        <Loader size="sm" />
      ) : items.length === 0 ? (
        <Paper withBorder>
          <EmptyState title={tr('Keine Fälle für diese Auswahl.', 'No cases for this selection.')} />
        </Paper>
      ) : (
        <Stack gap={8}>
          {items.map((c) => (
            <UnstyledButton
              key={c.id}
              onClick={() => navigate(`/app/reports/${c.id}`)}
              style={{ display: 'block', width: '100%' }}
            >
              <Paper withBorder p="md" className="manage-nav-row">
                <Group gap="sm" wrap="nowrap" align="flex-start">
                  <KindIcon kind={c.kind} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Group gap={8} wrap="wrap" justify="space-between" align="flex-start">
                      <Text fw={600} size="sm" style={{ wordBreak: 'break-word', flex: 1, minWidth: 160 }}>
                        <Text span c="dimmed" size="sm">
                          #{c.id}
                        </Text>{' '}
                        {c.title}
                      </Text>
                      <Group gap={6} wrap="nowrap">
                        {c.awaitingReply && (
                          <Badge color="red" variant="filled" size="sm">
                            {tr('Neue Antwort', 'New reply')}
                          </Badge>
                        )}
                        {c.severity === 'blocking' && c.status !== 'done' && c.status !== 'closed' && (
                          <Badge color="red" variant="light" size="sm">
                            {severityLabel(c.severity)}
                          </Badge>
                        )}
                        {c.isPublic && (
                          <Badge variant="outline" size="sm">
                            {tr('Roadmap', 'Roadmap')}
                          </Badge>
                        )}
                        <StatusBadge status={c.status} />
                      </Group>
                    </Group>
                    <Text size="xs" c="dimmed" mt={4}>
                      {[
                        c.reporter?.name ?? tr('Unbekannt', 'Unknown'),
                        c.club?.name,
                        areaLabel(c.area),
                        deviceText(c.fingerprint),
                        formatDate(c.createdAt),
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </Text>
                    <Group gap={12} mt={4}>
                      {c.kind === 'feature' && (
                        <Group gap={2}>
                          <IconArrowBigUp size={14} />
                          <Text size="xs">{c.votes}</Text>
                        </Group>
                      )}
                      {c.commentCount > 0 && (
                        <Group gap={2}>
                          <IconMessageCircle size={14} />
                          <Text size="xs">{c.commentCount}</Text>
                        </Group>
                      )}
                      {c.mergedInto && (
                        <Text size="xs" c="dimmed">
                          {tr('zusammengeführt mit', 'merged into')} #{c.mergedInto.id}
                        </Text>
                      )}
                    </Group>
                  </div>
                </Group>
              </Paper>
            </UnstyledButton>
          ))}
        </Stack>
      )}
      {data && data.total > perPage && (
        <Pagination
          page={page}
          perPage={perPage}
          total={data.total}
          totalPages={Math.ceil(data.total / perPage)}
          goPage={setPage}
          setPerPage={(n) => {
            setPerPage(n)
            setPage(1)
          }}
        />
      )}
    </div>
  )
}

function Section({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <Paper withBorder p="lg">
      <Group justify="space-between" mb={10} wrap="nowrap">
        <Text fw={700}>{title}</Text>
        {right}
      </Group>
      {children}
    </Paper>
  )
}

function Pre({ children }: { children: React.ReactNode }) {
  return (
    <Text size="sm" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {children}
    </Text>
  )
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ minWidth: 0 }}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="sm" style={{ wordBreak: 'break-word' }}>
        {children}
      </Text>
    </div>
  )
}

function CaseDetail({ id }: { id: number }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { notify } = useAdmin()
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(false)
  const [merging, setMerging] = useState(false)
  const query = useQuery({ queryKey: ['support-case', id], queryFn: () => getCase(id) })
  const c = query.data
  const plan = useQuery({ queryKey: ['roadmap'], queryFn: getRoadmap, enabled: c?.kind === 'feature' })
  const planned = (plan.data?.items ?? []).filter((i) => i.source !== 'idea')

  const refresh = async (fresh?: StaffCase) => {
    if (fresh) queryClient.setQueryData(['support-case', fresh.id], fresh)
    await queryClient.invalidateQueries({ queryKey: ['support-cases'] })
    if (!fresh || fresh.id !== id) await queryClient.invalidateQueries({ queryKey: ['support-case', id] })
  }

  const patch = async (body: Parameters<typeof updateCase>[1], done?: string) => {
    setSaving(true)
    try {
      await refresh(await updateCase(id, body))
      if (done) notify('success', done)
    } catch (err) {
      notify('error', tr('Speichern fehlgeschlagen', 'Save failed'), (err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (query.isLoading) return <Loader size="sm" />
  if (!c)
    return (
      <Text size="sm" c="dimmed">
        {tr('Fall nicht gefunden.', 'Case not found.')}
      </Text>
    )

  const fp = c.fingerprint
  const merged = !!c.mergedInto

  return (
    <div>
      <Button
        variant="subtle"
        leftSection={<IconArrowLeft size={16} />}
        onClick={() => navigate('/app/reports')}
        mb={8}
        px={6}
      >
        {tr('Alle Fälle', 'All cases')}
      </Button>
      <Group gap="sm" wrap="nowrap" align="flex-start" mb={6}>
        <KindIcon kind={c.kind} size={40} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <Title order={2} fz={22} style={{ wordBreak: 'break-word' }}>
            <Text span c="dimmed" inherit>
              #{c.id}
            </Text>{' '}
            {c.title}
          </Title>
          <Group gap={6} mt={6} wrap="wrap">
            <StatusBadge status={c.status} />
            <Badge variant="light" color={KIND_COLOR[c.kind]} size="sm">
              {kindLabel(c.kind)}
            </Badge>
            {c.severity && (
              <Badge variant="light" color={c.severity === 'blocking' ? 'red' : 'gray'} size="sm">
                {severityLabel(c.severity)}
              </Badge>
            )}
            {c.area && (
              <Badge variant="outline" color="gray" size="sm">
                {areaLabel(c.area)}
              </Badge>
            )}
          </Group>
        </div>
      </Group>

      {c.mergedInto && (
        <Paper withBorder p="sm" my={12} bg="var(--mantine-color-gray-light)">
          <Text size="sm">
            {tr('Zusammengeführt mit', 'Merged into')}{' '}
            <Anchor onClick={() => navigate(`/app/reports/${c.mergedInto!.id}`)}>
              #{c.mergedInto.id} {c.mergedInto.title}
            </Anchor>
          </Text>
        </Paper>
      )}

      <div className="support-detail-grid">
        <Stack gap={16} style={{ minWidth: 0 }}>
          <Section
            title={
              c.kind === 'bug'
                ? tr('Was ist passiert?', 'What happened?')
                : c.kind === 'feature'
                  ? tr('Die Idee', 'The idea')
                  : tr('Die Frage', 'The question')
            }
            right={
              <Button size="xs" variant="subtle" leftSection={<IconPencil size={14} />} onClick={() => setEditing(true)}>
                {tr('Bearbeiten', 'Edit')}
              </Button>
            }
          >
            <Pre>{c.description}</Pre>
            {c.steps && (
              <>
                <Text size="xs" fw={700} c="dimmed" mt={14} mb={4} tt="uppercase">
                  {tr('Schritte', 'Steps')}
                </Text>
                <Pre>{c.steps}</Pre>
              </>
            )}
            {c.expected && (
              <>
                <Text size="xs" fw={700} c="dimmed" mt={14} mb={4} tt="uppercase">
                  {tr('Erwartet', 'Expected')}
                </Text>
                <Pre>{c.expected}</Pre>
              </>
            )}
            {c.useCase && (
              <>
                <Text size="xs" fw={700} c="dimmed" mt={14} mb={4} tt="uppercase">
                  {tr('Wofür', 'What for')}
                </Text>
                <Pre>{c.useCase}</Pre>
              </>
            )}
          </Section>
          <Conversation c={c} onSent={() => refresh()} />
        </Stack>

        <Stack gap={16} style={{ minWidth: 0 }}>
          <Section title={tr('Bearbeiten', 'Handle')}>
            <Stack gap={12}>
              <Select
                label={tr('Status', 'Status')}
                value={c.status}
                disabled={merged || saving}
                allowDeselect={false}
                data={STATUSES.map((s) => ({ value: s, label: statusLabel(s) }))}
                onChange={(v) => v && v !== c.status && void patch({ status: v as CaseStatus }, tr('Status geändert', 'Status changed'))}
                description={tr('Die meldende Person bekommt eine Mail.', 'The reporter gets a mail.')}
              />
              {c.kind === 'feature' && (
                <Switch
                  label={tr('Auf der öffentlichen Roadmap', 'On the public roadmap')}
                  description={tr(
                    'Titel, Text, Status und Stimmen werden öffentlich; wer es gemeldet hat und der Verein nicht.',
                    'Title, text, status and votes become public; who reported it and the club do not.',
                  )}
                  checked={c.isPublic}
                  disabled={merged || saving}
                  onChange={(e) => void patch({ isPublic: e.currentTarget.checked })}
                />
              )}
              {c.kind === 'feature' && (
                <Select
                  label={tr('Teil eines geplanten Eintrags', 'Part of a planned item')}
                  description={tr(
                    'Auf der Roadmap erscheint dann der geplante Eintrag; die Stimmen dieser Idee zählen für ihn.',
                    'The roadmap then shows the planned item; this idea’s votes count for it.',
                  )}
                  placeholder={tr('Keiner', 'None')}
                  clearable
                  searchable
                  value={c.roadmapItem}
                  disabled={merged || saving}
                  data={planned.map((p) => ({ value: p.id, label: `${pickTitle(p.title)} (${p.status})` }))}
                  onChange={(v) =>
                    (v ?? null) !== c.roadmapItem &&
                    void patch({ roadmapItem: v ?? null }, tr('Roadmap-Eintrag gespeichert', 'Roadmap item saved'))
                  }
                />
              )}
              <Button
                variant="default"
                leftSection={<IconGitMerge size={16} />}
                disabled={merged}
                onClick={() => setMerging(true)}
              >
                {tr('Mit anderem Fall zusammenführen …', 'Merge into another case…')}
              </Button>
            </Stack>
          </Section>
          <PeopleSection c={c} onChange={refresh} />
          <Section title={tr('Details', 'Details')}>
            <SimpleGrid cols={2} spacing={12} verticalSpacing={10}>
              <Fact label={tr('Von', 'From')}>
                {c.reporter ? (
                  <>
                    {c.reporter.name}
                    <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                      {c.reporter.email}
                    </Text>
                    {c.reporter.guest && (
                      <Badge size="xs" variant="light" color="gray" mt={4}>
                        {c.reporter.reason === 'wrong_recipient'
                          ? tr('Ohne Konto · Mail an falsche Person', 'No account · mail to the wrong person')
                          : c.reporter.reason === 'unwanted_mail'
                            ? tr('Ohne Konto · will keine Mails', 'No account · wants no mails')
                            : tr('Ohne Konto', 'No account')}
                        {c.reporter.mail ? ` · ${c.reporter.mail}` : ''}
                      </Badge>
                    )}
                  </>
                ) : (
                  '–'
                )}
              </Fact>
              <Fact label={tr('Verein', 'Club')}>{c.club?.name ?? '–'}</Fact>
              <Fact label={tr('Gemeldet', 'Reported')}>{formatDateTime(c.createdAt)}</Fact>
              {c.kind === 'feature' ? <Fact label={tr('Stimmen', 'Votes')}>{c.votes}</Fact> : <Fact label={tr('Seite', 'Page')}>{c.page ?? '–'}</Fact>}
              {c.kind === 'feature' && c.page && <Fact label={tr('Seite', 'Page')}>{c.page}</Fact>}
              {c.closedAt && <Fact label={tr('Abgeschlossen', 'Finished')}>{formatDateTime(c.closedAt)}</Fact>}
            </SimpleGrid>
          </Section>
          <Section title={tr('Gerät', 'Device')}>
            <SimpleGrid cols={2} spacing={12} verticalSpacing={10}>
              <Fact label="Browser">{[fp.browser, fp.browserVersion].filter(Boolean).join(' ') || '–'}</Fact>
              <Fact label={tr('Betriebssystem', 'OS')}>{[fp.os, fp.osVersion].filter(Boolean).join(' ') || '–'}</Fact>
              <Fact label={tr('Gerät', 'Device')}>
                {fp.deviceType
                  ? { phone: tr('Handy', 'Phone'), tablet: 'Tablet', desktop: tr('Computer', 'Computer') }[fp.deviceType]
                  : '–'}
              </Fact>
              <Fact label={tr('Bildschirm', 'Screen')}>
                {fp.screenWidth ? `${fp.screenWidth} × ${fp.screenHeight}` : '–'}
              </Fact>
              <Fact label={tr('Fenster', 'Window')}>
                {fp.viewportWidth ? `${fp.viewportWidth} × ${fp.viewportHeight}` : '–'}
              </Fact>
              <Fact label={tr('Sprache / Darstellung', 'Language / theme')}>
                {[fp.language, fp.theme === 'dark' ? tr('dunkel', 'dark') : fp.theme === 'light' ? tr('hell', 'light') : null]
                  .filter(Boolean)
                  .join(' · ') || '–'}
              </Fact>
              <Fact label={tr('Hubra-Version', 'Hubra version')}>{fp.appVersion ?? '–'}</Fact>
            </SimpleGrid>
          </Section>
          {(c.merged ?? []).length > 0 && (
            <Section title={tr('Zusammengeführt', 'Merged here')}>
              <Stack gap={4}>
                {c.merged!.map((m) => (
                  <Anchor key={m.id} size="sm" onClick={() => navigate(`/app/reports/${m.id}`)}>
                    #{m.id} {m.title}
                  </Anchor>
                ))}
              </Stack>
            </Section>
          )}
        </Stack>
      </div>

      {editing && (
        <EditModal
          c={c}
          onClose={() => setEditing(false)}
          onSave={async (body) => {
            await patch(body, tr('Gespeichert', 'Saved'))
            setEditing(false)
          }}
        />
      )}
      {merging && (
        <MergeModal
          c={c}
          onClose={() => setMerging(false)}
          onMerged={async (target) => {
            setMerging(false)
            await refresh(target)
            navigate(`/app/reports/${target.id}`)
          }}
        />
      )}
    </div>
  )
}

const DISCORD_STATE: Record<Exclude<DiscordState, ''>, { color: string; de: string; en: string }> = {
  added: { color: 'green', de: 'Im Thread', en: 'In the thread' },
  invited: { color: 'orange', de: 'Eingeladen', en: 'Invited' },
  no_discord: { color: 'gray', de: 'Kein Discord', en: 'No Discord' },
  failed: { color: 'red', de: 'Fehlgeschlagen', en: 'Failed' },
}

function DiscordBadge({ p }: { p: CasePerson }) {
  if (!p.discord) return null
  const s = DISCORD_STATE[p.discord]
  return (
    <Badge size="xs" variant="light" color={s.color} leftSection={<IconBrandDiscord size={11} />}>
      {tr(s.de, s.en)}
    </Badge>
  )
}

/** Who is on the case (reporter + people staff added) and its Discord thread. */
function PeopleSection({ c, onChange }: { c: StaffCase; onChange: (fresh?: StaffCase) => Promise<void> }) {
  const { notify } = useAdmin()
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const people = c.people ?? []
  const discord = c.discord
  const merged = !!c.mergedInto

  const run = async (key: string, fn: () => Promise<StaffCase>, done?: string) => {
    setBusy(key)
    try {
      await onChange(await fn())
      if (done) notify('success', done)
    } catch (err) {
      notify('error', tr('Das hat nicht geklappt', 'That did not work'), (err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Section
      title={tr('Personen', 'People')}
      right={
        <Button
          size="xs"
          variant="subtle"
          leftSection={<IconUserPlus size={14} />}
          disabled={merged}
          onClick={() => setAdding(true)}
        >
          {tr('Hinzufügen', 'Add')}
        </Button>
      }
    >
      <Stack gap={10}>
        {people.length === 0 && (
          <Text size="sm" c="dimmed">
            {tr('Niemand.', 'Nobody.')}
          </Text>
        )}
        {people.map((p) => (
          <Group key={p.id} gap="xs" wrap="nowrap" align="flex-start" justify="space-between">
            <div style={{ minWidth: 0 }}>
              <Group gap={6} wrap="wrap">
                <Text size="sm" fw={500}>
                  {p.name}
                </Text>
                {p.reporter && (
                  <Badge size="xs" variant="outline" color="gray">
                    {tr('meldet', 'reporter')}
                  </Badge>
                )}
                <DiscordBadge p={p} />
              </Group>
              <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                {p.email}
              </Text>
              {p.discord === 'invited' && p.inviteUrl && (
                <Text size="xs" c="dimmed">
                  {tr('Einladung: ', 'Invite: ')}
                  <Anchor href={p.inviteUrl} target="_blank" rel="noreferrer" size="xs">
                    {p.inviteUrl.replace('https://', '')}
                  </Anchor>
                </Text>
              )}
            </div>
            {p.reporter && !p.added && discord?.enabled && p.discordLinked ? (
              <Button
                size="compact-xs"
                variant="light"
                loading={busy === `add-${p.id}`}
                disabled={merged}
                onClick={() =>
                  void run(`add-${p.id}`, () => addPeople(c.id, [p.id]), tr('Wird zum Thread hinzugefügt', 'Being added to the thread'))
                }
              >
                {tr('In den Thread', 'Add to thread')}
              </Button>
            ) : (
              !p.reporter && (
                <Button
                  size="compact-xs"
                  variant="subtle"
                  color="gray"
                  aria-label={tr('Entfernen', 'Remove')}
                  loading={busy === `rm-${p.id}`}
                  onClick={() => void run(`rm-${p.id}`, () => removePerson(c.id, p.id))}
                >
                  <IconX size={14} />
                </Button>
              )
            )}
          </Group>
        ))}
        <Text size="xs" c="dimmed">
          {tr(
            'Hinzugefügte sehen den Fall auf der Support-Seite, können antworten und bekommen Antworten und Statuswechsel wie die meldende Person.',
            'People you add see the case on the support site, can answer, and get answers and status changes like the reporter.',
          )}
        </Text>
        {discord?.enabled ? (
          discord.threadId ? (
            <Group gap="xs">
              {discord.threadUrl && (
                <Button
                  component="a"
                  href={discord.threadUrl}
                  target="_blank"
                  rel="noreferrer"
                  size="xs"
                  variant="light"
                  leftSection={<IconBrandDiscord size={14} />}
                >
                  {tr('Thread öffnen', 'Open thread')}
                </Button>
              )}
              <Button
                size="xs"
                variant="subtle"
                loading={busy === 'thread'}
                disabled={merged}
                onClick={() =>
                  void run('thread', () => openThread(c.id), tr('Personen werden erneut hinzugefügt', 'Adding people again'))
                }
              >
                {tr('Personen erneut hinzufügen', 'Add people again')}
              </Button>
            </Group>
          ) : (
            <Button
              size="xs"
              variant="light"
              leftSection={<IconBrandDiscord size={14} />}
              loading={busy === 'thread'}
              disabled={merged}
              onClick={() =>
                void run('thread', () => openThread(c.id), tr('Thread wird angelegt', 'Opening the thread'))
              }
            >
              {tr('Discord-Thread anlegen', 'Open a Discord thread')}
            </Button>
          )
        ) : (
          <Text size="xs" c="dimmed">
            {tr(
              'Discord-Threads: Support-Kanal unter Discord › Kanäle wählen.',
              'Discord threads: pick a support channel under Discord › Channels.',
            )}
          </Text>
        )}
      </Stack>
      {adding && (
        <AddPeopleModal
          c={c}
          onClose={() => setAdding(false)}
          onAdded={async (fresh) => {
            setAdding(false)
            await onChange(fresh)
            notify('success', tr('Hinzugefügt', 'Added'))
          }}
        />
      )}
    </Section>
  )
}

function AddPeopleModal({
  c,
  onClose,
  onAdded,
}: {
  c: StaffCase
  onClose: () => void
  onAdded: (fresh: StaffCase) => Promise<void>
}) {
  const { notify } = useAdmin()
  const [search, setSearch] = useState('')
  const [debounced] = useDebouncedValue(search.trim(), 250)
  const [picked, setPicked] = useState<Record<string, Account>>({})
  const [saving, setSaving] = useState(false)
  const found = useQuery({
    queryKey: ['support-accounts', debounced],
    queryFn: () => findAccounts(debounced),
    enabled: debounced.length >= 2,
  })
  const onCase = new Set((c.people ?? []).filter((p) => p.added || !p.reporter).map((p) => p.id))
  const options = new Map<string, Account>()
  for (const a of Object.values(picked)) options.set(String(a.id), a)
  for (const a of found.data?.items ?? []) if (!onCase.has(a.id)) options.set(String(a.id), a)

  const save = async () => {
    setSaving(true)
    try {
      await onAdded(await addPeople(c.id, Object.values(picked).map((a) => a.id)))
    } catch (err) {
      notify('error', tr('Hinzufügen fehlgeschlagen', 'Adding failed'), (err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal opened onClose={onClose} title={tr('Personen hinzufügen', 'Add people')}>
      <Stack gap="md">
        <MultiSelect
          label={tr('Konten', 'Accounts')}
          description={tr('Name oder E-Mail, mindestens zwei Zeichen.', 'Name or e-mail, at least two characters.')}
          placeholder={tr('Suchen …', 'Search…')}
          searchable
          searchValue={search}
          onSearchChange={setSearch}
          filter={({ options: all }) => all}
          nothingFoundMessage={debounced.length >= 2 && !found.isFetching ? tr('Niemand gefunden', 'Nobody found') : undefined}
          data={[...options.values()].map((a) => ({ value: String(a.id), label: `${a.name} · ${a.email}` }))}
          value={Object.keys(picked)}
          onChange={(ids) =>
            setPicked(Object.fromEntries(ids.map((id) => [id, options.get(id)!]).filter(([, a]) => a)))
          }
          maxValues={20}
          data-autofocus
        />
        <Text size="xs" c="dimmed">
          {tr(
            'Mit verknüpftem Discord kommen sie in den Thread des Falls; wer nicht auf dem Plattform-Server ist, bekommt eine Einladung als Direktnachricht.',
            'With Discord linked they join the case’s thread; anyone not on the platform server gets an invite as a direct message.',
          )}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button onClick={() => void save()} loading={saving} disabled={Object.keys(picked).length === 0}>
            {tr('Hinzufügen', 'Add')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function Conversation({ c, onSent }: { c: StaffCase; onSent: () => Promise<void> }) {
  const { notify } = useAdmin()
  const [body, setBody] = useState('')
  const [internal, setInternal] = useState(false)
  const [sending, setSending] = useState(false)
  const comments = c.comments ?? []

  const send = async () => {
    if (!body.trim()) return
    setSending(true)
    try {
      await commentOnCase(c.id, body.trim(), internal)
      setBody('')
      await onSent()
      notify(
        'success',
        internal ? tr('Notiz gespeichert', 'Note saved') : tr('Antwort gesendet', 'Answer sent'),
      )
    } catch (err) {
      notify('error', tr('Senden fehlgeschlagen', 'Sending failed'), (err as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <Section title={tr('Verlauf', 'Conversation')}>
      <Stack gap={10}>
        {comments.length === 0 && (
          <Text size="sm" c="dimmed">
            {tr('Noch keine Kommentare.', 'No comments yet.')}
          </Text>
        )}
        {comments.map((m) => (
          <Paper
            key={m.id}
            p="sm"
            withBorder={m.internal}
            style={m.internal ? { borderStyle: 'dashed' } : undefined}
            bg={m.internal ? undefined : m.fromStaff ? 'var(--mantine-color-acc-light)' : 'var(--mantine-color-gray-light)'}
          >
            <Group gap={6} mb={2}>
              {m.internal && <IconLock size={12} />}
              <Text size="xs" fw={600} c="dimmed">
                {m.author ?? (m.fromStaff ? tr('Team', 'Team') : tr('Meldende Person', 'Reporter'))}
                {m.internal ? ` · ${tr('intern', 'internal')}` : m.fromStaff ? '' : ` · ${tr('meldende Person', 'reporter')}`} ·{' '}
                {formatDateTime(m.createdAt)}
              </Text>
            </Group>
            <Pre>{m.body}</Pre>
          </Paper>
        ))}
        <Textarea
          value={body}
          onChange={(e) => setBody(e.currentTarget.value)}
          placeholder={
            internal
              ? tr('Notiz für das Team …', 'Note for the team…')
              : tr('Antwort an die meldende Person …', 'Answer to the reporter…')
          }
          autosize
          minRows={3}
          maxRows={10}
          maxLength={5000}
          mt={4}
        />
        <Group justify="space-between" wrap="wrap" gap="sm">
          <Checkbox
            label={tr('Interne Notiz (nicht sichtbar, keine Mail)', 'Internal note (not shown, no mail)')}
            checked={internal}
            onChange={(e) => setInternal(e.currentTarget.checked)}
          />
          <Button onClick={() => void send()} loading={sending} disabled={!body.trim()}>
            {internal ? tr('Notiz speichern', 'Save note') : tr('Antworten', 'Answer')}
          </Button>
        </Group>
      </Stack>
    </Section>
  )
}

function EditModal({
  c,
  onClose,
  onSave,
}: {
  c: StaffCase
  onClose: () => void
  onSave: (body: { title: string; description: string }) => Promise<void>
}) {
  const [title, setTitle] = useState(c.title)
  const [description, setDescription] = useState(c.description)
  const [saving, setSaving] = useState(false)
  return (
    <Modal opened onClose={onClose} title={tr('Fall bearbeiten', 'Edit case')} size="lg">
      <Stack gap={12}>
        <Text size="xs" c="dimmed">
          {tr(
            'Zum Beispiel vor dem Veröffentlichen auf der Roadmap: klarer Titel, keine persönlichen Angaben im Text.',
            'For example before putting it on the roadmap: a clear title, nothing personal in the text.',
          )}
        </Text>
        <TextInput label={tr('Titel', 'Title')} value={title} maxLength={200} onChange={(e) => setTitle(e.currentTarget.value)} />
        <Textarea
          label={tr('Text', 'Text')}
          value={description}
          onChange={(e) => setDescription(e.currentTarget.value)}
          autosize
          minRows={4}
          maxRows={14}
          maxLength={5000}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            loading={saving}
            disabled={!title.trim() || !description.trim()}
            onClick={async () => {
              setSaving(true)
              try {
                await onSave({ title: title.trim(), description: description.trim() })
              } finally {
                setSaving(false)
              }
            }}
          >
            {tr('Speichern', 'Save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function MergeModal({
  c,
  onClose,
  onMerged,
}: {
  c: StaffCase
  onClose: () => void
  onMerged: (target: StaffCase) => Promise<void>
}) {
  const { notify } = useAdmin()
  const [search, setSearch] = useState('')
  const [q] = useDebouncedValue(search.trim(), 250)
  const [target, setTarget] = useState<StaffCase | null>(null)
  const [saving, setSaving] = useState(false)
  const query = useQuery({
    queryKey: ['support-cases', 'merge', c.kind, q],
    queryFn: () => listCases({ kind: c.kind, q, perPage: 20 }),
  })
  const options = (query.data?.items ?? []).filter((i) => i.id !== c.id && !i.mergedInto)

  return (
    <Modal opened onClose={onClose} title={tr('Zusammenführen', 'Merge')} size="lg">
      <Stack gap={12}>
        <Text size="sm">
          {tr(
            `#${c.id} wird geschlossen und zeigt auf den gewählten Fall. Stimmen gehen mit, und die meldende Person bekommt eine Mail.`,
            `#${c.id} is closed and points to the case you pick. Votes move along, and the reporter gets a mail.`,
          )}
        </Text>
        <TextInput
          leftSection={<IconSearch size={16} />}
          placeholder={tr('Fall suchen: Titel oder #Nummer', 'Find a case: title or #number')}
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          data-autofocus
        />
        <Stack gap={6} mah={320} style={{ overflowY: 'auto' }}>
          {options.map((o) => (
            <UnstyledButton key={o.id} onClick={() => setTarget(o)}>
              <Paper
                withBorder
                p="sm"
                style={target?.id === o.id ? { borderColor: 'var(--mantine-color-acc-6)', borderWidth: 2 } : undefined}
              >
                <Group justify="space-between" wrap="nowrap" gap="xs">
                  <Text size="sm" style={{ wordBreak: 'break-word' }}>
                    <Text span c="dimmed" size="sm">
                      #{o.id}
                    </Text>{' '}
                    {o.title}
                  </Text>
                  <StatusBadge status={o.status} />
                </Group>
              </Paper>
            </UnstyledButton>
          ))}
          {!query.isLoading && options.length === 0 && (
            <Text size="sm" c="dimmed">
              {tr('Kein passender Fall.', 'No matching case.')}
            </Text>
          )}
        </Stack>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            leftSection={<IconGitMerge size={16} />}
            disabled={!target}
            loading={saving}
            onClick={async () => {
              if (!target) return
              setSaving(true)
              try {
                const merged = await mergeCase(c.id, target.id)
                notify('success', tr(`In #${target.id} zusammengeführt`, `Merged into #${target.id}`))
                await onMerged(merged)
              } catch (err) {
                notify('error', tr('Zusammenführen fehlgeschlagen', 'Merge failed'), (err as Error).message)
              } finally {
                setSaving(false)
              }
            }}
          >
            {target ? tr(`In #${target.id} zusammenführen`, `Merge into #${target.id}`) : tr('Zusammenführen', 'Merge')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
