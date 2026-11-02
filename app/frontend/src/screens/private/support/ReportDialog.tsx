import { useMemo, useState, useSyncExternalStore } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Collapse,
  Group,
  Select,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  UnstyledButton,
} from '@mantine/core'
import { IconBug, IconBulb, IconChevronDown, IconChevronRight, IconDeviceDesktop } from '@tabler/icons-react'
import { Modal, Field } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'
import { AREAS, sendCase, type Area, type CaseKind, type Severity } from '@/api/support'
import { currentDeviceInfo, type DeviceInfo } from './deviceInfo'
import { openReport, reportKind, subscribeReport } from './reportStore'
import { deviceLines } from './labels'

/** "Problem melden" / "Idee vorschlagen": one dialog, opened from the account menu. */
export function ReportDialog() {
  const kind = useSyncExternalStore(subscribeReport, reportKind)
  return kind ? <ReportForm key={kind} initialKind={kind} /> : null
}

function ReportForm({ initialKind }: { initialKind: CaseKind }) {
  const { t } = useT()
  const { notify } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<CaseKind>(initialKind)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [steps, setSteps] = useState('')
  const [expected, setExpected] = useState('')
  const [useCase, setUseCase] = useState('')
  const [area, setArea] = useState<Area | null>(null)
  const [severity, setSeverity] = useState<Severity>('annoying')
  const [showDevice, setShowDevice] = useState(false)
  const [errors, setErrors] = useState<{ title?: string; description?: string }>({})
  const [sending, setSending] = useState(false)
  // Read once, when the dialog opens: the window the problem happened in.
  const [device] = useState<DeviceInfo>(() => currentDeviceInfo())
  const page = location.pathname

  const areaOptions = useMemo(
    () => AREAS.map((a) => ({ value: a, label: t(`support.area.${a}`) })),
    [t],
  )
  const bug = kind === 'bug'
  const close = () => openReport(null)

  const submit = async () => {
    const next: typeof errors = {}
    if (!title.trim()) next.title = t('support.form.titleRequired', 'Bitte gib einen kurzen Titel ein.')
    if (!description.trim())
      next.description = bug
        ? t('support.form.whatHappenedRequired', 'Bitte beschreibe, was passiert ist.')
        : t('support.form.ideaRequired', 'Bitte beschreibe deine Idee.')
    setErrors(next)
    if (Object.keys(next).length) return
    setSending(true)
    try {
      const created = await sendCase({
        kind,
        title: title.trim(),
        description: description.trim(),
        ...(bug
          ? { steps: steps.trim(), expected: expected.trim(), severity }
          : { useCase: useCase.trim() }),
        area,
        page,
        fingerprint: device,
      })
      await queryClient.invalidateQueries({ queryKey: qk.support.mine })
      close()
      notify(
        'success',
        bug ? t('support.form.sentBug', 'Problem gemeldet') : t('support.form.sentIdea', 'Idee gesendet'),
        t('support.form.sentMsg', 'Danke! Du findest sie unter Meldungen als #{{id}}.', { id: created.id }),
      )
    } catch (err) {
      notify('error', t('support.form.sendFailed', 'Senden fehlgeschlagen'), (err as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <Modal
      open
      onClose={close}
      wide
      title={bug ? t('support.form.bugTitle', 'Problem melden') : t('support.form.ideaTitle', 'Idee vorschlagen')}
      subtitle={
        bug
          ? t('support.form.bugSub', 'Etwas funktioniert nicht wie erwartet? Das Hubra-Team schaut es sich an.')
          : t('support.form.ideaSub', 'Was würde dir oder deinem Verein die Arbeit erleichtern?')
      }
      onSubmit={(e) => {
        e?.preventDefault()
        void submit()
      }}
      footer={
        <>
          <Button
            variant="subtle"
            onClick={() => {
              close()
              navigate('/app/feedback')
            }}
          >
            {t('support.form.myReports', 'Meine Meldungen')}
          </Button>
          <Button variant="default" onClick={close}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button type="submit" loading={sending}>
            {t('support.form.send', 'Senden')}
          </Button>
        </>
      }
    >
      <SegmentedControl
        fullWidth
        value={kind}
        onChange={(v) => {
          setKind(v as CaseKind)
          setErrors({})
        }}
        data={[
          {
            value: 'bug',
            label: (
              <Group gap={6} justify="center" wrap="nowrap">
                <IconBug size={16} />
                {t('support.kind.bug', 'Problem')}
              </Group>
            ),
          },
          {
            value: 'feature',
            label: (
              <Group gap={6} justify="center" wrap="nowrap">
                <IconBulb size={16} />
                {t('support.kind.feature', 'Idee')}
              </Group>
            ),
          },
        ]}
      />
      <Field label={t('support.form.title', 'Titel')}>
        <TextInput
          value={title}
          maxLength={200}
          onChange={(e) => setTitle(e.currentTarget.value)}
          placeholder={
            bug
              ? t('support.form.titlePhBug', 'z. B. Rechnung lässt sich nicht speichern')
              : t('support.form.titlePhIdea', 'z. B. Anlässe als Kalender abonnieren')
          }
          error={errors.title}
          data-autofocus
        />
      </Field>
      <Field
        label={
          bug
            ? t('support.form.whatHappened', 'Was ist passiert?')
            : t('support.form.idea', 'Was wünschst du dir?')
        }
      >
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.currentTarget.value)}
          autosize
          minRows={3}
          maxRows={10}
          maxLength={5000}
          placeholder={
            bug
              ? t('support.form.whatHappenedPh', 'Beschreibe den Fehler und eine Fehlermeldung, falls eine kam.')
              : t('support.form.ideaPh', 'Beschreibe, was Hubra können sollte.')
          }
          error={errors.description}
        />
      </Field>
      {bug ? (
        <>
          <Field
            label={t('support.form.steps', 'Wie kommt man dahin?')}
            hint={t('support.form.stepsHint', 'Die Schritte nacheinander, damit wir es nachstellen können.')}
          >
            <Textarea
              value={steps}
              onChange={(e) => setSteps(e.currentTarget.value)}
              autosize
              minRows={3}
              maxRows={8}
              maxLength={5000}
              placeholder={t('support.form.stepsPh', '1. Finanzen öffnen\n2. Neue Rechnung\n3. Speichern')}
            />
          </Field>
          <Field label={t('support.form.expected', 'Was hättest du erwartet?')}>
            <Textarea
              value={expected}
              onChange={(e) => setExpected(e.currentTarget.value)}
              autosize
              minRows={2}
              maxRows={6}
              maxLength={5000}
            />
          </Field>
        </>
      ) : (
        <Field
          label={t('support.form.useCase', 'Wofür brauchst du das?')}
          hint={t('support.form.useCaseHint', 'Das Problem dahinter hilft uns, die beste Lösung zu finden.')}
        >
          <Textarea
            value={useCase}
            onChange={(e) => setUseCase(e.currentTarget.value)}
            autosize
            minRows={2}
            maxRows={8}
            maxLength={5000}
          />
        </Field>
      )}
      <SimpleGrid cols={{ base: 1, sm: bug ? 2 : 1 }} spacing={12}>
        <Field label={t('support.form.area', 'Bereich')}>
          <Select
            data={areaOptions}
            value={area}
            onChange={(v) => setArea((v as Area) || null)}
            clearable
            placeholder={t('support.form.areaPh', 'Optional')}
            comboboxProps={{ withinPortal: true }}
          />
        </Field>
        {bug && (
          <Field label={t('support.form.severity', 'Wie schlimm ist es?')}>
            <Select
              data={[
                { value: 'minor', label: t('support.severity.minor', 'Kleinigkeit') },
                { value: 'annoying', label: t('support.severity.annoying', 'Stört bei der Arbeit') },
                { value: 'blocking', label: t('support.severity.blocking', 'Ich komme nicht weiter') },
              ]}
              value={severity}
              onChange={(v) => v && setSeverity(v as Severity)}
              allowDeselect={false}
              comboboxProps={{ withinPortal: true }}
            />
          </Field>
        )}
      </SimpleGrid>
      <Alert variant="light" color="gray" p="sm" icon={<IconDeviceDesktop size={18} />}>
        <UnstyledButton
          onClick={() => setShowDevice((v) => !v)}
          aria-expanded={showDevice}
          style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}
        >
          <Text size="sm" fw={600} style={{ flex: 1 }}>
            {t('support.device.sent', 'Wird mitgeschickt: Browser, Gerät und Bildschirmgrösse')}
          </Text>
          {showDevice ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
        </UnstyledButton>
        <Collapse expanded={showDevice}>
          <Stack gap={2} mt={8}>
            {deviceLines(device, t, page).map(([label, value]) => (
              <Text key={label} size="xs">
                <Text span c="dimmed" size="xs">
                  {label}:
                </Text>{' '}
                {value}
              </Text>
            ))}
            <Text size="xs" c="dimmed" mt={4}>
              {t('support.device.only', 'Nur das. Keine Adresse, keine weiteren Merkmale des Geräts.')}
            </Text>
          </Stack>
        </Collapse>
      </Alert>
    </Modal>
  )
}
