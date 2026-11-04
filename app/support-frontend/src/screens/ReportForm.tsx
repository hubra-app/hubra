import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Anchor,
  Button,
  Collapse,
  Group,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
} from '@mantine/core'
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { currentDeviceInfo, type DeviceInfo } from '@hubra/ui'
import { Page } from '@/components/Layout'
import { SignInNeeded } from '@/components/SignInNeeded'
import { useAuth } from '@/auth'
import { useLang } from '@/lang'
import { AREAS, myClubs, sendCaseFor, type Area, type CaseKind, type Severity } from '@/api/support'
import { areaLabel, deviceLines, pathOf, severityLabel } from '@/lib/labels'

/**
 * /melden, /idee and /kontakt: one form, three kinds. A problem asks how to
 * get there and what was expected, and sends the device info (shown before
 * sending); an idea asks what it is for; a question is just the question.
 */
export function ReportScreen({ kind }: { kind: CaseKind }) {
  const { tr } = useLang()
  const { status } = useAuth()
  const copy = {
    bug: {
      title: tr('Problem melden', 'Report a problem'),
      intro: tr(
        'Etwas funktioniert nicht wie erwartet? Beschreibe es so genau wie möglich; das Hubra-Team schaut es sich an und antwortet dir per Mail.',
        'Something not working as expected? Describe it as closely as you can; the Hubra team looks into it and answers you by mail.',
      ),
    },
    feature: {
      title: tr('Idee vorschlagen', 'Suggest an idea'),
      intro: tr(
        'Was würde dir oder deinem Verein die Arbeit erleichtern? Gute Ideen kommen auf die Roadmap, wo alle dafür stimmen können.',
        'What would make work easier for you or your club? Good ideas go on the roadmap, where everyone can vote for them.',
      ),
    },
    question: {
      title: tr('Kontakt', 'Contact'),
      intro: tr(
        'Eine Frage zu Hubra, zu deinem Verein auf Hubra, zu Preisen oder Datenschutz? Schreib uns; die Antwort kommt per Mail und steht unter «Meine Meldungen».',
        'A question about Hubra, your club on Hubra, pricing or privacy? Write to us; the answer comes by mail and shows under "My reports".',
      ),
    },
  }[kind]

  return (
    <Page narrow title={copy.title} intro={copy.intro}>
      {status === 'authed' ? (
        <ReportForm kind={kind} />
      ) : (
        <Stack gap="lg">
          <SignInNeeded
            why={tr(
              'Damit wir dir antworten können, braucht es dein Hubra-Konto.',
              'We need your Hubra account so we can answer you.',
            )}
          />
          {kind === 'question' && status === 'anon' && (
            <Text size="sm" c="dimmed">
              {tr('Noch kein Konto? Schreib an', 'No account yet? Write to')}{' '}
              <Anchor href="mailto:hi@hubra.club">hi@hubra.club</Anchor>.
            </Text>
          )}
        </Stack>
      )}
    </Page>
  )
}

function ReportForm({ kind }: { kind: CaseKind }) {
  const { tr } = useLang()
  const { notify } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const initialArea = AREAS.includes(params.get('area') as Area) ? (params.get('area') as Area) : null
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [steps, setSteps] = useState('')
  const [expected, setExpected] = useState('')
  const [useCase, setUseCase] = useState('')
  const [where, setWhere] = useState('')
  const [area, setArea] = useState<Area | null>(initialArea)
  const [severity, setSeverity] = useState<Severity>('annoying')
  const [club, setClub] = useState<string | null>(params.get('club'))
  const [showDevice, setShowDevice] = useState(false)
  const [errors, setErrors] = useState<{ title?: string; description?: string }>({})
  const [sending, setSending] = useState(false)
  const [device] = useState<DeviceInfo>(() => currentDeviceInfo())
  const clubs = useQuery({ queryKey: ['my-clubs'], queryFn: myClubs })
  const bug = kind === 'bug'

  const areaOptions = useMemo(() => AREAS.map((a) => ({ value: a, label: areaLabel(tr, a) })), [tr])
  const clubOptions = (clubs.data ?? []).map((c) => ({ value: c.tenant_slug, label: c.tenant_name }))

  const submit = async () => {
    const next: typeof errors = {}
    if (!title.trim()) next.title = tr('Bitte gib einen kurzen Titel ein.', 'Please enter a short title.')
    if (!description.trim())
      next.description =
        kind === 'bug'
          ? tr('Bitte beschreibe, was passiert ist.', 'Please describe what happened.')
          : kind === 'feature'
            ? tr('Bitte beschreibe deine Idee.', 'Please describe your idea.')
            : tr('Bitte schreib deine Frage.', 'Please write your question.')
    setErrors(next)
    if (Object.keys(next).length) return
    setSending(true)
    try {
      const created = await sendCaseFor(
        {
          kind,
          title: title.trim(),
          description: description.trim(),
          ...(bug
            ? { steps: steps.trim(), expected: expected.trim(), severity, page: pathOf(where), fingerprint: device }
            : kind === 'feature'
              ? { useCase: useCase.trim() }
              : {}),
          area,
        },
        clubOptions.some((c) => c.value === club) ? club : null,
      )
      notify(
        'success',
        tr('Gesendet', 'Sent'),
        tr(`Danke! Du findest es unter Meine Meldungen als #${created.id}.`, `Thank you! You'll find it under My reports as #${created.id}.`),
      )
      navigate(`/meine/${created.id}`)
    } catch (err) {
      notify('error', tr('Senden fehlgeschlagen', 'Sending failed'), (err as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <Paper withBorder radius="lg" p={{ base: 'md', sm: 'xl' }}>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <Stack gap="md">
          <TextInput
            label={kind === 'question' ? tr('Betreff', 'Subject') : tr('Titel', 'Title')}
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.currentTarget.value)}
            placeholder={
              bug
                ? tr('z. B. Rechnung lässt sich nicht speichern', 'e.g. Invoice cannot be saved')
                : kind === 'feature'
                  ? tr('z. B. Anlässe als Kalender abonnieren', 'e.g. Subscribe to events as a calendar')
                  : tr('z. B. Frage zu den Preisen', 'e.g. Question about pricing')
            }
            error={errors.title}
            data-autofocus
            required
          />
          <Textarea
            label={
              bug
                ? tr('Was ist passiert?', 'What happened?')
                : kind === 'feature'
                  ? tr('Was wünschst du dir?', 'What would you like?')
                  : tr('Deine Frage', 'Your question')
            }
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
            autosize
            minRows={4}
            maxRows={12}
            maxLength={5000}
            placeholder={
              bug
                ? tr('Beschreibe den Fehler und eine Fehlermeldung, falls eine kam.', 'Describe the error, and the error message if there was one.')
                : kind === 'feature'
                  ? tr('Beschreibe, was Hubra können sollte.', 'Describe what Hubra should be able to do.')
                  : undefined
            }
            error={errors.description}
            required
          />
          {bug && (
            <>
              <Textarea
                label={tr('Wie kommt man dahin?', 'How do you get there?')}
                description={tr('Die Schritte nacheinander, damit wir es nachstellen können.', 'The steps one after the other, so we can reproduce it.')}
                value={steps}
                onChange={(e) => setSteps(e.currentTarget.value)}
                autosize
                minRows={3}
                maxRows={8}
                maxLength={5000}
                placeholder={tr('1. Finanzen öffnen\n2. Neue Rechnung\n3. Speichern', '1. Open Finance\n2. New invoice\n3. Save')}
              />
              <Textarea
                label={tr('Was hättest du erwartet?', 'What did you expect?')}
                value={expected}
                onChange={(e) => setExpected(e.currentTarget.value)}
                autosize
                minRows={2}
                maxRows={6}
                maxLength={5000}
              />
              <TextInput
                label={tr('Wo ist es passiert?', 'Where did it happen?')}
                description={tr('Die Adresse der Seite in der Vereins-App, falls du sie hast.', 'The address of the page in the club app, if you have it.')}
                value={where}
                onChange={(e) => setWhere(e.currentTarget.value)}
                placeholder="https://app.hubra.club/…"
                maxLength={500}
              />
            </>
          )}
          {kind === 'feature' && (
            <Textarea
              label={tr('Wofür brauchst du das?', 'What do you need it for?')}
              description={tr('Das Problem dahinter hilft uns, die beste Lösung zu finden.', 'The problem behind it helps us find the best solution.')}
              value={useCase}
              onChange={(e) => setUseCase(e.currentTarget.value)}
              autosize
              minRows={2}
              maxRows={8}
              maxLength={5000}
            />
          )}
          <SimpleGrid cols={{ base: 1, sm: bug ? 3 : 2 }} spacing="md">
            <Select
              label={tr('Verein', 'Club')}
              data={clubOptions}
              value={club}
              onChange={setClub}
              clearable
              placeholder={clubOptions.length ? tr('Optional', 'Optional') : tr('Kein Verein', 'No club')}
              disabled={!clubOptions.length}
            />
            <Select
              label={tr('Bereich', 'Area')}
              data={areaOptions}
              value={area}
              onChange={(v) => setArea((v as Area) || null)}
              clearable
              placeholder={tr('Optional', 'Optional')}
            />
            {bug && (
              <Select
                label={tr('Wie schlimm ist es?', 'How bad is it?')}
                data={(['minor', 'annoying', 'blocking'] as Severity[]).map((s) => ({ value: s, label: severityLabel(tr, s) }))}
                value={severity}
                onChange={(v) => setSeverity((v as Severity) || 'annoying')}
                allowDeselect={false}
              />
            )}
          </SimpleGrid>
          {bug && (
            <Paper withBorder radius="md" p="sm" bg="var(--hb-surface-2)">
              <Anchor component="button" type="button" size="sm" onClick={() => setShowDevice((v) => !v)}>
                <Group gap={4} wrap="nowrap">
                  {showDevice ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
                  {tr('Diese Angaben zum Gerät werden mitgeschickt', 'This device info is sent along')}
                </Group>
              </Anchor>
              <Collapse expanded={showDevice}>
                <Table mt="xs" fz="sm" withRowBorders={false} verticalSpacing={2}>
                  <Table.Tbody>
                    {deviceLines(device, tr).map(([k, v]) => (
                      <Table.Tr key={k}>
                        <Table.Td c="dimmed" w={160}>
                          {k}
                        </Table.Td>
                        <Table.Td>{v}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
                <Text size="xs" c="dimmed" mt={4}>
                  {tr(
                    'Nur das, keine IP-Adresse und kein Fingerabdruck des Browsers.',
                    'Only this, no IP address and no browser fingerprint.',
                  )}
                </Text>
              </Collapse>
            </Paper>
          )}
          <Group justify="space-between" mt={4}>
            <Anchor component={Link} to="/meine" size="sm">
              {tr('Meine Meldungen', 'My reports')}
            </Anchor>
            <Button type="submit" loading={sending}>
              {tr('Senden', 'Send')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Paper>
  )
}
