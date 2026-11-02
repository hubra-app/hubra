import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Code,
  CopyButton,
  FileButton,
  Group,
  List,
  Modal,
  Paper,
  PasswordInput,
  Stack,
  Stepper,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import {
  IconAlertTriangle,
  IconCheck,
  IconCopy,
  IconDownload,
  IconKey,
  IconLock,
  IconShieldCheck,
  IconUpload,
} from '@tabler/icons-react'
import { generateX25519Identity, identityToRecipient } from 'age-encryption'
import { PUBLIC_RE, keyFile, keyFileMatches } from '@/screens/private/settings/backupKey'
import { getBackupKey, removeBackupKey, setBackupKey, type BackupKeyState } from '@/api/admin'
import { useAuth, useToast } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'
import { formatDateTime } from '@/format'
import { ErrorBanner } from '@/components/ui'

// The club's own backup key is an age key pair. The private key is made here,
// in the browser, and never sent to Hubra: the server only gets the public
// key and encrypts every new backup of the club to it as well as to the
// platform's key. So the club can open its own backups, and losing the key
// costs the club that access but not its data.

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function KeyLine({ value }: { value: string }) {
  const { t } = useT()
  return (
    <Group gap={6} wrap="nowrap" align="flex-start">
      <Code block style={{ flex: 1, minWidth: 0, wordBreak: 'break-all', whiteSpace: 'pre-wrap' }}>
        {value}
      </Code>
      <CopyButton value={value}>
        {({ copied, copy }) => (
          <Button
            size="xs"
            variant="default"
            onClick={copy}
            leftSection={copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
          >
            {copied ? t('backupKey.copied', 'Kopiert') : t('backupKey.copy', 'Kopieren')}
          </Button>
        )}
      </CopyButton>
    </Group>
  )
}

/** Paste or upload a key file and check, only in the browser, that it fits. */
function KeyCheck({
  publicKey,
  onResult,
}: {
  publicKey: string
  onResult: (ok: boolean) => void
}) {
  const { t } = useT()
  const [text, setText] = useState('')
  const [result, setResult] = useState<'ok' | 'wrong' | null>(null)

  const check = async (value: string) => {
    setText(value)
    if (!value.trim()) {
      setResult(null)
      onResult(false)
      return
    }
    const ok = await keyFileMatches(value, publicKey)
    setResult(ok ? 'ok' : 'wrong')
    onResult(ok)
  }

  return (
    <Stack gap={10}>
      <Textarea
        label={t('backupKey.check.label', 'Privater Schlüssel oder Inhalt der Schlüsseldatei')}
        placeholder="AGE-SECRET-KEY-1…"
        autosize
        minRows={2}
        value={text}
        onChange={(e) => void check(e.currentTarget.value)}
        styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
        autoComplete="off"
        spellCheck={false}
      />
      <Group gap="xs">
        <FileButton onChange={(f) => f && void f.text().then(check)} accept=".txt,.key,text/plain">
          {(props) => (
            <Button {...props} variant="light" size="xs" leftSection={<IconUpload size={14} />}>
              {t('backupKey.check.upload', 'Schlüsseldatei wählen')}
            </Button>
          )}
        </FileButton>
        <Text fz="xs" c="dimmed">
          {t('backupKey.check.local', 'Die Prüfung läuft nur in diesem Browser; nichts davon wird gesendet.')}
        </Text>
      </Group>
      {result === 'ok' && (
        <Alert color="green" icon={<IconCheck size={18} />}>
          {t('backupKey.check.ok', 'Passt: Das ist der private Schlüssel zu diesem öffentlichen Schlüssel.')}
        </Alert>
      )}
      {result === 'wrong' && (
        <Alert color="red" icon={<IconAlertTriangle size={18} />}>
          {t(
            'backupKey.check.wrong',
            'Passt nicht. Das ist nicht der private Schlüssel zu diesem öffentlichen Schlüssel, oder die Datei ist unvollständig.',
          )}
        </Alert>
      )}
    </Stack>
  )
}

function WhatItIs() {
  const { t } = useT()
  return (
    <Stack gap={10}>
      <Text>
        {t(
          'backupKey.intro.p1',
          'Hubra sichert die Daten deines Vereins jede Nacht. Die Backups sind verschlüsselt, und bisher kann sie nur der Betreiber von Hubra öffnen.',
        )}
      </Text>
      <Text>
        {t(
          'backupKey.intro.p2',
          'Mit einem eigenen Schlüssel wird jedes neue Backup zusätzlich für euch verschlüsselt. Dann könnt ihr eure Backups selbst öffnen, zum Beispiel wenn ihr Hubra einmal verlasst oder eine Kopie eurer Daten ausserhalb von Hubra aufbewahren wollt.',
        )}
      </Text>
      <List spacing={6} size="sm" icon={<IconLock size={16} />}>
        <List.Item>
          {t(
            'backupKey.intro.pair',
            'Der Schlüssel besteht aus zwei Teilen: Den öffentlichen Schlüssel (age1…) bekommt Hubra, damit es Backups für euch verschliessen kann. Den privaten Schlüssel (AGE-SECRET-KEY-1…) behaltet nur ihr; nur er öffnet die Backups.',
          )}
        </List.Item>
        <List.Item>
          {t(
            'backupKey.intro.browser',
            'Der Schlüssel wird hier in deinem Browser erzeugt. Der private Teil wird nie an Hubra gesendet, und Hubra kann ihn nicht wiederherstellen.',
          )}
        </List.Item>
        <List.Item>
          {t(
            'backupKey.intro.loss',
            'Geht der private Schlüssel verloren, verliert ihr keine Daten: Hubra kann eure Backups weiterhin mit dem eigenen Schlüssel wiederherstellen. Ihr könnt sie nur nicht mehr selbst öffnen.',
          )}
        </List.Item>
      </List>
    </Stack>
  )
}

/** The guided flow: explain, generate, store, confirm. */
function KeyWizard({ onDone, onCancel, replacing }: { onDone: () => void; onCancel?: () => void; replacing: boolean }) {
  const { t } = useT()
  const { notify } = useToast()
  const { tenantSlug } = useAuth()
  const phone = useMediaQuery('(max-width: 48em)')
  const [step, setStep] = useState(0)
  const [pair, setPair] = useState<{ priv: string; pub: string } | null>(null)
  const [own, setOwn] = useState(false)
  const [ownKey, setOwnKey] = useState('')
  const [stored, setStored] = useState(false)
  const [kept, setKept] = useState(false)
  const [saved, setSaved] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [saving, setSaving] = useState(false)

  // A fresh private key that is not confirmed yet would be gone on reload.
  useEffect(() => {
    if (!pair || step > 3) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [pair, step])

  const generate = async () => {
    const priv = await generateX25519Identity()
    const pub = await identityToRecipient(priv)
    setPair({ priv, pub })
    setOwn(false)
    setSaved(false)
    setStored(false)
    setConfirmed(false)
    setStep(1)
  }

  const club = tenantSlug ?? 'club'
  const fileName = `hubra-${club}-backup-key.txt`

  const activate = async (publicKey: string) => {
    setSaving(true)
    try {
      await setBackupKey(publicKey)
      // The private key is no longer needed on this page.
      setPair(null)
      setStep(4)
      notify('success', t('backupKey.activated', 'Backup-Schlüssel aktiviert'))
    } catch (err) {
      notify(
        'error',
        t('backupKey.activateFailed', 'Schlüssel konnte nicht gespeichert werden'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      setSaving(false)
    }
  }

  const ownValid = PUBLIC_RE.test(ownKey.trim())
  const ownIsPrivate = /AGE-SECRET-KEY/i.test(ownKey)

  return (
    <Paper withBorder p="lg">
      <Group gap="xs" mb="md" wrap="nowrap">
        <IconKey size={22} style={{ flexShrink: 0 }} />
        <Title order={3}>
          {replacing
            ? t('backupKey.wizard.replaceTitle', 'Neuen Backup-Schlüssel einrichten')
            : t('backupKey.wizard.title', 'Eigenen Backup-Schlüssel einrichten')}
        </Title>
      </Group>
      <Stepper
        active={step}
        size="sm"
        allowNextStepsSelect={false}
        onStepClick={(s) => s < step && step < 4 && setStep(s)}
      >
        <Stepper.Step label={phone ? undefined : t('backupKey.step.about', 'Worum es geht')}>
          {phone && (
            <Text fw={700} mt="md">
              {t('backupKey.stepOf', 'Schritt {{n}} von 4: {{label}}', { n: 1, label: t('backupKey.step.about', 'Worum es geht') })}
            </Text>
          )}
          <Stack gap="md" mt="md">
            <WhatItIs />
            {replacing && (
              <Alert color="yellow" icon={<IconAlertTriangle size={18} />}>
                {t(
                  'backupKey.wizard.replaceHint',
                  'Backups, die schon gemacht wurden, öffnen weiterhin nur mit dem bisherigen Schlüssel. Bewahrt ihn deshalb auf, bis diese Backups abgelaufen sind.',
                )}
              </Alert>
            )}
            {own ? (
              <Stack gap={8}>
                <Textarea
                  label={t('backupKey.own.label', 'Öffentlicher Schlüssel (age1…)')}
                  description={t(
                    'backupKey.own.hint',
                    'Zum Beispiel aus «age-keygen» oder einem Passwortmanager, der age-Schlüssel erzeugt. Nur den öffentlichen Teil einfügen.',
                  )}
                  placeholder="age1…"
                  autosize
                  minRows={1}
                  value={ownKey}
                  onChange={(e) => setOwnKey(e.currentTarget.value)}
                  error={
                    ownIsPrivate
                      ? t(
                          'backupKey.own.private',
                          'Das ist der private Schlüssel. Er gehört nicht hierher; füge nur den öffentlichen Schlüssel (age1…) ein.',
                        )
                      : ownKey.trim() && !ownValid
                        ? t('backupKey.own.invalid', 'Das ist kein öffentlicher age-Schlüssel (age1…).')
                        : undefined
                  }
                  styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
                  spellCheck={false}
                />
                <Group justify="flex-end">
                  <Button variant="default" onClick={() => setOwn(false)}>
                    {t('common.back', 'Zurück')}
                  </Button>
                  <Button
                    disabled={!ownValid || ownIsPrivate}
                    loading={saving}
                    onClick={() => void activate(ownKey.trim())}
                  >
                    {t('backupKey.own.save', 'Diesen Schlüssel verwenden')}
                  </Button>
                </Group>
              </Stack>
            ) : (
              <Group justify="space-between">
                <Group gap="xs">
                  {onCancel && (
                    <Button variant="default" onClick={onCancel}>
                      {t('common.cancel', 'Abbrechen')}
                    </Button>
                  )}
                  <Button variant="subtle" onClick={() => setOwn(true)}>
                    {t('backupKey.own.open', 'Ich habe schon einen age-Schlüssel')}
                  </Button>
                </Group>
                <Button leftSection={<IconKey size={16} />} onClick={() => void generate()}>
                  {t('backupKey.generate', 'Schlüssel erzeugen')}
                </Button>
              </Group>
            )}
          </Stack>
        </Stepper.Step>

        <Stepper.Step label={phone ? undefined : t('backupKey.step.generate', 'Erzeugen')}>
          {phone && (
            <Text fw={700} mt="md">
              {t('backupKey.stepOf', 'Schritt {{n}} von 4: {{label}}', { n: 2, label: t('backupKey.step.generate', 'Erzeugen') })}
            </Text>
          )}
          {pair && (
            <Stack gap="md" mt="md">
              <Text>
                {t(
                  'backupKey.generated',
                  'Euer Schlüsselpaar ist erzeugt. Es existiert im Moment nur in diesem Browserfenster.',
                )}
              </Text>
              <div>
                <Text fw={600} fz="sm" mb={4}>
                  {t('backupKey.publicLabel', 'Öffentlicher Schlüssel (bekommt Hubra)')}
                </Text>
                <KeyLine value={pair.pub} />
              </div>
              <div>
                <Text fw={600} fz="sm" mb={4}>
                  {t('backupKey.privateLabel', 'Privater Schlüssel (nur für euch)')}
                </Text>
                <PasswordInput
                  readOnly
                  value={pair.priv}
                  aria-label={t('backupKey.privateLabel', 'Privater Schlüssel (nur für euch)')}
                  styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
                />
              </div>
              <Group justify="space-between">
                <Button variant="default" onClick={() => setStep(0)}>
                  {t('common.back', 'Zurück')}
                </Button>
                <Button onClick={() => setStep(2)}>{t('backupKey.next.store', 'Weiter: aufbewahren')}</Button>
              </Group>
            </Stack>
          )}
        </Stepper.Step>

        <Stepper.Step label={phone ? undefined : t('backupKey.step.store', 'Aufbewahren')}>
          {phone && (
            <Text fw={700} mt="md">
              {t('backupKey.stepOf', 'Schritt {{n}} von 4: {{label}}', { n: 3, label: t('backupKey.step.store', 'Aufbewahren') })}
            </Text>
          )}
          {pair && (
            <Stack gap="md" mt="md">
              <Text>
                {t(
                  'backupKey.store.intro',
                  'Speichere die Schlüsseldatei jetzt an einem sicheren Ort. Sobald du diese Seite verlässt, ist der private Schlüssel hier weg.',
                )}
              </Text>
              <Group gap="xs">
                <Button
                  leftSection={<IconDownload size={16} />}
                  onClick={() => {
                    download(fileName, keyFile(pair.priv, pair.pub, club))
                    setSaved(true)
                  }}
                >
                  {t('backupKey.store.download', 'Schlüsseldatei herunterladen')}
                </Button>
                <CopyButton value={keyFile(pair.priv, pair.pub, club)}>
                  {({ copied, copy }) => (
                    <Button
                      variant="default"
                      leftSection={copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                      onClick={() => {
                        copy()
                        setSaved(true)
                      }}
                    >
                      {copied
                        ? t('backupKey.copied', 'Kopiert')
                        : t('backupKey.store.copy', 'Für den Passwortmanager kopieren')}
                    </Button>
                  )}
                </CopyButton>
              </Group>
              <Paper withBorder p="md" bg="var(--mantine-color-body)">
                <Text fw={600} mb={6}>
                  {t('backupKey.store.howTitle', 'So bewahrt ihr ihn sicher auf')}
                </Text>
                <List spacing={6} size="sm">
                  <List.Item>
                    {t(
                      'backupKey.store.manager',
                      'Am besten in einem Passwortmanager des Vereins (z. B. Bitwarden, 1Password oder KeePass) als sichere Notiz oder Anhang.',
                    )}
                  </List.Item>
                  <List.Item>
                    {t(
                      'backupKey.store.second',
                      'Eine zweite Kopie bei einer anderen Person im Vorstand oder ausgedruckt an einem sicheren Ort, damit der Schlüssel nicht an einer Person hängt.',
                    )}
                  </List.Item>
                  <List.Item>
                    {t(
                      'backupKey.store.never',
                      'Nicht per E-Mail oder Chat verschicken, nicht in Hubra ablegen und nicht offen in einem geteilten Ordner speichern.',
                    )}
                  </List.Item>
                  <List.Item>
                    {t(
                      'backupKey.store.delete',
                      'Hast du die Datei heruntergeladen und in den Passwortmanager übernommen, lösche sie aus dem Download-Ordner.',
                    )}
                  </List.Item>
                </List>
              </Paper>
              <Stack gap={6}>
                <Checkbox
                  checked={stored}
                  disabled={!saved}
                  onChange={(e) => setStored(e.currentTarget.checked)}
                  label={t('backupKey.store.ack', 'Ich habe den privaten Schlüssel sicher gespeichert.')}
                />
                <Checkbox
                  checked={kept}
                  disabled={!saved}
                  onChange={(e) => setKept(e.currentTarget.checked)}
                  label={t(
                    'backupKey.store.ackLoss',
                    'Ich weiss, dass Hubra den privaten Schlüssel nicht kennt und nicht wiederherstellen kann.',
                  )}
                />
              </Stack>
              <Group justify="space-between">
                <Button variant="default" onClick={() => setStep(1)}>
                  {t('common.back', 'Zurück')}
                </Button>
                <Button disabled={!saved || !stored || !kept} onClick={() => setStep(3)}>
                  {t('backupKey.next.confirm', 'Weiter: bestätigen')}
                </Button>
              </Group>
            </Stack>
          )}
        </Stepper.Step>

        <Stepper.Step label={phone ? undefined : t('backupKey.step.confirm', 'Bestätigen')}>
          {phone && (
            <Text fw={700} mt="md">
              {t('backupKey.stepOf', 'Schritt {{n}} von 4: {{label}}', { n: 4, label: t('backupKey.step.confirm', 'Bestätigen') })}
            </Text>
          )}
          {pair && (
            <Stack gap="md" mt="md">
              <Text>
                {t(
                  'backupKey.confirm.intro',
                  'Zeig, dass der gespeicherte Schlüssel stimmt: Öffne ihn dort, wo du ihn abgelegt hast, und füge ihn hier ein oder wähle die Datei. Erst dann wird der Schlüssel aktiviert.',
                )}
              </Text>
              <KeyCheck publicKey={pair.pub} onResult={setConfirmed} />
              <Group justify="space-between">
                <Button variant="default" onClick={() => setStep(2)}>
                  {t('common.back', 'Zurück')}
                </Button>
                <Button
                  disabled={!confirmed}
                  loading={saving}
                  leftSection={<IconShieldCheck size={16} />}
                  onClick={() => void activate(pair.pub)}
                >
                  {t('backupKey.activate', 'Schlüssel aktivieren')}
                </Button>
              </Group>
            </Stack>
          )}
        </Stepper.Step>

        <Stepper.Completed>
          <Stack gap="md" mt="md">
            <Alert color="green" icon={<IconCheck size={18} />} title={t('backupKey.done.title', 'Fertig')}>
              {t(
                'backupKey.done.text',
                'Ab dem nächsten Backup wird jede Sicherung eures Vereins auch mit eurem Schlüssel verschlüsselt.',
              )}
            </Alert>
            <Group justify="flex-end">
              <Button onClick={onDone}>{t('backupKey.done.close', 'Zur Übersicht')}</Button>
            </Group>
          </Stack>
        </Stepper.Completed>
      </Stepper>
    </Paper>
  )
}

function KeyStatus({
  state,
  onReplace,
}: {
  state: BackupKeyState & { public_key: string }
  onReplace: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [checkOpen, setCheckOpen] = useState(false)
  const [removeOpen, setRemoveOpen] = useState(false)
  const [removing, setRemoving] = useState(false)

  const remove = async () => {
    setRemoving(true)
    try {
      await removeBackupKey()
      notify('success', t('backupKey.removed', 'Backup-Schlüssel entfernt'))
      setRemoveOpen(false)
      void queryClient.invalidateQueries({ queryKey: qk.settings.backupKey })
    } catch (err) {
      notify('error', t('backupKey.removeFailed', 'Schlüssel konnte nicht entfernt werden'), err instanceof Error ? err.message : undefined)
    } finally {
      setRemoving(false)
    }
  }

  return (
    <Stack gap={20}>
      <Paper withBorder p="lg">
        <Group justify="space-between" mb="md" wrap="wrap" gap="xs">
          <Group gap="xs">
            <IconShieldCheck size={22} color="var(--mantine-color-green-6)" />
            <Title order={3}>{t('backupKey.status.title', 'Eigener Backup-Schlüssel')}</Title>
          </Group>
          <Badge color="green" variant="light">
            {t('backupKey.status.active', 'Aktiv')}
          </Badge>
        </Group>
        <Stack gap="sm">
          <div>
            <Text fw={600} fz="sm" mb={4}>
              {t('backupKey.publicKey', 'Öffentlicher Schlüssel')}
            </Text>
            <KeyLine value={state.public_key} />
          </div>
          {state.set_at && (
            <Text fz="sm" c="dimmed">
              {state.set_by
                ? t('backupKey.status.setBy', 'Eingerichtet am {{date}} von {{name}}', {
                    date: formatDateTime(state.set_at),
                    name: state.set_by,
                  })
                : t('backupKey.status.setAt', 'Eingerichtet am {{date}}', { date: formatDateTime(state.set_at) })}
            </Text>
          )}
          {!state.backups_use_key ? (
            <Alert color="yellow" icon={<IconAlertTriangle size={18} />}>
              {t(
                'backupKey.status.notYet',
                'Dieser Server verschlüsselt Backups noch nicht mit öffentlichen Schlüsseln. Euer Schlüssel ist gespeichert und gilt, sobald der Betreiber das umstellt.',
              )}
            </Alert>
          ) : state.last_backup_with_key ? (
            <Text fz="sm">
              {t('backupKey.status.lastBackup', 'Letztes Backup mit eurem Schlüssel: {{date}}', {
                date: formatDateTime(state.last_backup_with_key),
              })}
            </Text>
          ) : (
            <Text fz="sm">
              {t('backupKey.status.nextBackup', 'Das nächste Backup wird mit eurem Schlüssel verschlüsselt.')}
            </Text>
          )}
          <Group gap="xs" mt="xs">
            <Button variant="light" leftSection={<IconKey size={16} />} onClick={() => setCheckOpen(true)}>
              {t('backupKey.status.check', 'Gespeicherten Schlüssel prüfen')}
            </Button>
            <Button variant="default" onClick={onReplace}>
              {t('backupKey.status.replace', 'Neuen Schlüssel erzeugen')}
            </Button>
            <Button variant="subtle" color="red" onClick={() => setRemoveOpen(true)}>
              {t('backupKey.status.remove', 'Schlüssel entfernen')}
            </Button>
          </Group>
        </Stack>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={4} mb="sm">
          {t('backupKey.open.title', 'So öffnet ihr ein Backup')}
        </Title>
        <Stack gap={8}>
          <Text fz="sm">
            {t(
              'backupKey.open.file',
              'Eine Backup-Datei (endet auf .dump.age) bekommt ihr vom Betreiber eurer Hubra-Installation. Geöffnet wird sie mit dem kostenlosen Programm age (age-encryption.org):',
            )}
          </Text>
          <Code block>{'age --decrypt -i hubra-backup-key.txt -o verein.dump backup.dump.age'}</Code>
          <Text fz="sm">
            {t(
              'backupKey.open.restore',
              'Die entschlüsselte Datei ist ein PostgreSQL-Dump; mit pg_restore lässt sie sich in eine eigene Datenbank einspielen.',
            )}
          </Text>
        </Stack>
      </Paper>

      <Modal
        opened={checkOpen}
        onClose={() => setCheckOpen(false)}
        title={t('backupKey.status.check', 'Gespeicherten Schlüssel prüfen')}
        size="lg"
      >
        <Stack gap="sm">
          <Text fz="sm">
            {t(
              'backupKey.check.intro',
              'Prüft, ob der Schlüssel, den ihr aufbewahrt, zu diesem Verein passt. Am besten einmal im Jahr oder wenn jemand im Vorstand wechselt.',
            )}
          </Text>
          <KeyCheck publicKey={state.public_key} onResult={() => {}} />
        </Stack>
      </Modal>

      <Modal
        opened={removeOpen}
        onClose={() => setRemoveOpen(false)}
        title={t('backupKey.status.remove', 'Schlüssel entfernen')}
      >
        <Stack gap="md">
          <Text fz="sm">
            {t(
              'backupKey.removeConfirm',
              'Neue Backups werden dann nur noch mit dem Schlüssel des Betreibers verschlüsselt. Backups, die schon gemacht wurden, öffnen weiterhin mit eurem privaten Schlüssel; bewahrt ihn also auf.',
            )}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRemoveOpen(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button color="red" loading={removing} onClick={() => void remove()}>
              {t('backupKey.status.remove', 'Schlüssel entfernen')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}

export function BackupKeyTab() {
  const { t } = useT()
  const queryClient = useQueryClient()
  const [replacing, setReplacing] = useState(false)
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: qk.settings.backupKey,
    queryFn: getBackupKey,
  })

  if (isLoading) return null
  if (error || !data)
    return (
      <ErrorBanner
        message={t('backupKey.loadFailed', 'Der Backup-Schlüssel konnte nicht geladen werden.')}
        onRetry={() => void refetch()}
      />
    )

  const done = () => {
    setReplacing(false)
    void queryClient.invalidateQueries({ queryKey: qk.settings.backupKey })
  }

  if (data.public_key && !replacing)
    return <KeyStatus state={{ ...data, public_key: data.public_key }} onReplace={() => setReplacing(true)} />

  return (
    <KeyWizard
      key={replacing ? 'replace' : 'new'}
      replacing={replacing}
      onDone={done}
      onCancel={replacing ? () => setReplacing(false) : undefined}
    />
  )
}
