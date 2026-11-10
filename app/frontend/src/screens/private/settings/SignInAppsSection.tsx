import { useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  CopyButton,
  Group,
  Paper,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { IconCheck, IconCopy } from '@tabler/icons-react'
import {
  createClubSignInApp,
  deleteClubSignInApp,
  editClubSignInApp,
  listClubSignInApps,
  newClubSignInAppSecret,
  type ClubSignInApp,
  type NewClubSignInApp,
} from '@/api/apiTokens'
import { ConfirmModal, Modal } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDateTime } from '@/format'
import { useT } from '@/locales/i18n'

export function Copyable({ label, value, testId }: { label: string; value: string; testId?: string }) {
  const { t } = useT()
  return (
    <Stack gap={2}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Group gap={6} wrap="nowrap">
        <Text ff="monospace" fz="sm" style={{ wordBreak: 'break-all' }} data-testid={testId}>
          {value}
        </Text>
        <CopyButton value={value} timeout={2000}>
          {({ copied, copy }) => (
            <ActionIcon
              color={copied ? 'teal' : 'gray'}
              variant="subtle"
              onClick={copy}
              aria-label={copied ? t('common.copied') : t('common.copy')}
            >
              {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
            </ActionIcon>
          )}
        </CopyButton>
      </Group>
    </Stack>
  )
}

/** Client ID and, once, the secret of a new app, with the setup addresses. */
function CredentialsModal({
  app,
  discoveryUrl,
  onClose,
}: {
  app: NewClubSignInApp | null
  discoveryUrl: string
  onClose: () => void
}) {
  const { t } = useT()
  return (
    <Modal
      open={app !== null}
      onClose={onClose}
      title={t('signInApps.credentials', 'Zugangsdaten für die Website')}
      footer={<Button onClick={onClose}>{t('signInApps.done', 'Fertig')}</Button>}
    >
      {app && (
        <Stack gap="sm">
          <Copyable label={t('signInApps.discovery', 'Discovery-Adresse (OpenID Connect)')} value={discoveryUrl} />
          <Copyable label="Client ID" value={app.clientId} />
          {app.clientSecret ? (
            <>
              <Alert color="orange" variant="light" title={t('signInApps.onlyNow', 'Nur jetzt sichtbar')}>
                {t(
                  'signInApps.onlyNowBody',
                  'Hubra speichert nur einen Hash. Trage das Secret jetzt in der Website ein; danach lässt es sich nur noch ersetzen.',
                )}
              </Alert>
              <Copyable label="Client Secret" value={app.clientSecret} testId="new-client-secret" />
            </>
          ) : (
            <Text size="xs" c="dimmed">
              {t(
                'signInApps.public',
                'Ohne Secret: die Website oder App meldet Mitglieder nur mit PKCE an.',
              )}
            </Text>
          )}
        </Stack>
      )}
    </Modal>
  )
}

function AppModal({
  open,
  app,
  onClose,
  onSaved,
}: {
  open: boolean
  app: ClubSignInApp | null
  onClose: () => void
  onSaved: (made?: NewClubSignInApp) => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [name, setName] = useState(app?.name ?? '')
  const [description, setDescription] = useState(app?.description ?? '')
  const [clientUri, setClientUri] = useState(app?.clientUri ?? '')
  const [uris, setUris] = useState((app?.redirectUris ?? []).join('\n'))
  const [confidential, setConfidential] = useState(true)
  const [busy, setBusy] = useState(false)

  const submit = async (event?: FormEvent) => {
    // A form: without this the page reloads and a new secret is lost.
    event?.preventDefault()
    setBusy(true)
    const body = {
      name: name.trim(),
      description: description.trim(),
      clientUri: clientUri.trim() || null,
      redirectUris: uris
        .split(/[\s,]+/)
        .map((u) => u.trim())
        .filter(Boolean),
    }
    try {
      if (app) {
        await editClubSignInApp(app.id, body)
        onSaved()
      } else {
        onSaved(await createClubSignInApp({ ...body, confidential }))
      }
    } catch (err) {
      notify('error', t('signInApps.saveFailed', 'Nicht gespeichert'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={app ? t('signInApps.edit', 'Anmelde-App bearbeiten') : t('signInApps.new', 'Neue Anmelde-App')}
      subtitle={t(
        'signInApps.modalHint',
        'Mitglieder melden sich auf eurer Website mit ihrem Hubra-Konto an. Die Website liest nichts aus Hubra.',
      )}
      onSubmit={submit}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('signInApps.cancel', 'Abbrechen')}
          </Button>
          <Button type="submit" loading={busy} disabled={!name.trim() || !uris.trim()}>
            {app ? t('signInApps.save', 'Speichern') : t('signInApps.create', 'Erstellen')}
          </Button>
        </>
      }
    >
      <TextInput
        label={t('signInApps.name', 'Name')}
        description={t('signInApps.nameHint', 'So sehen Mitglieder die App beim Anmelden, z. B. «Vereinswebsite».')}
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        maxLength={100}
        required
        data-autofocus
      />
      <TextInput
        label={t('signInApps.website', 'Website (optional)')}
        placeholder="https://"
        value={clientUri}
        onChange={(e) => setClientUri(e.currentTarget.value)}
      />
      <Textarea
        label={t('signInApps.redirects', 'Rücksprung-Adressen')}
        description={t(
          'signInApps.redirectsHint',
          'Eine pro Zeile, genau so, wie die Website sie schickt (steht in der Anleitung des Plugins). Nur https.',
        )}
        placeholder="https://www.example.ch/openid-connect/callback"
        value={uris}
        onChange={(e) => setUris(e.currentTarget.value)}
        autosize
        minRows={2}
        required
      />
      <Textarea
        label={t('signInApps.description', 'Beschreibung (optional)')}
        value={description}
        onChange={(e) => setDescription(e.currentTarget.value)}
        maxLength={500}
        autosize
        minRows={2}
      />
      {!app && (
        <Checkbox
          label={t('signInApps.confidential', 'Mit Secret (Website mit Server, z. B. WordPress)')}
          description={t(
            'signInApps.confidentialHint',
            'Aus nur für Apps im Browser oder auf dem Handy: sie melden sich mit PKCE an.',
          )}
          checked={confidential}
          onChange={(e) => setConfidential(e.currentTarget.checked)}
        />
      )}
    </Modal>
  )
}

/**
 * Einstellungen › API & Webhooks › Anmelden mit Hubra (docs/oidc.md): the
 * club's website or forum signs members in with their Hubra account.
 */
export function SignInAppsSection() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const apps = useQuery({ queryKey: qk.settings.signInApps, queryFn: listClubSignInApps })
  const [editing, setEditing] = useState<ClubSignInApp | 'new' | null>(null)
  const [shown, setShown] = useState<NewClubSignInApp | null>(null)
  const [deleting, setDeleting] = useState<ClubSignInApp | null>(null)
  const [renewing, setRenewing] = useState<ClubSignInApp | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: qk.settings.signInApps })
  const fail = (title: string) => (err: unknown) =>
    notify('error', title, err instanceof Error ? err.message : undefined)

  const toggle = async (app: ClubSignInApp, on: boolean) => {
    try {
      await editClubSignInApp(app.id, { disabled: !on })
      await refresh()
    } catch (err) {
      fail(t('signInApps.saveFailed', 'Nicht gespeichert'))(err)
    }
  }

  const items = apps.data?.items ?? []
  const full = apps.data ? items.length >= apps.data.max : true

  return (
    <Paper withBorder p="lg">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div style={{ minWidth: 0 }}>
            <Title order={4}>{t('signInApps.title', 'Anmelden mit Hubra')}</Title>
            <Text size="sm" c="dimmed">
              {t(
                'signInApps.intro',
                'Eure Website, euer Forum oder eine andere App kann Mitglieder mit ihrem Hubra-Konto anmelden (OpenID Connect). Nur aktive Mitglieder des Vereins kommen hinein. Die App erfährt Name, E-Mail und Mitgliedschaft (Status, Admin, Gruppen), wenn das Mitglied zustimmt, und kann in Hubra nichts lesen.',
              )}
            </Text>
          </div>
          <Button size="sm" style={{ flexShrink: 0 }} disabled={full} onClick={() => setEditing('new')}>
            {t('signInApps.new', 'Neue Anmelde-App')}
          </Button>
        </Group>
        {apps.data && (
          <Copyable
            label={t('signInApps.discovery', 'Discovery-Adresse (OpenID Connect)')}
            value={apps.data.discoveryUrl}
          />
        )}
        {apps.data && items.length === 0 && (
          <Text size="sm" c="dimmed">
            {t('signInApps.none', 'Noch keine Anmelde-App.')}
          </Text>
        )}
        {items.map((app) => (
          <Paper key={app.id} withBorder p="md">
            <Stack gap={6}>
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <div style={{ minWidth: 0 }}>
                  <Group gap="xs" wrap="nowrap">
                    <Text fw={600} truncate>
                      {app.name}
                    </Text>
                    {app.disabledAt && (
                      <Badge size="sm" variant="light" color="gray">
                        {t('signInApps.off', 'aus')}
                      </Badge>
                    )}
                  </Group>
                  <Text size="xs" c="dimmed" ff="monospace" style={{ wordBreak: 'break-all' }}>
                    {app.clientId}
                  </Text>
                </div>
                <Switch
                  aria-label={t('signInApps.on', 'Aktiv')}
                  checked={!app.disabledAt}
                  onChange={(e) => void toggle(app, e.currentTarget.checked)}
                  style={{ flexShrink: 0 }}
                />
              </Group>
              <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                {app.redirectUris.join(' · ')}
              </Text>
              <Text size="xs" c="dimmed">
                {t('signInApps.signIns', 'Angemeldet: {{count}}', { count: app.activeGrants })} ·{' '}
                {app.lastUsedAt
                  ? `${t('signInApps.lastUsed', 'zuletzt')} ${formatDateTime(app.lastUsedAt)}`
                  : t('signInApps.unused', 'noch nicht genutzt')}
              </Text>
              <Group gap="xs">
                <Button size="xs" variant="default" onClick={() => setEditing(app)}>
                  {t('signInApps.editShort', 'Bearbeiten')}
                </Button>
                {app.confidential && (
                  <Button size="xs" variant="default" onClick={() => setRenewing(app)}>
                    {t('signInApps.newSecret', 'Neues Secret')}
                  </Button>
                )}
                <Button size="xs" variant="subtle" color="red" onClick={() => setDeleting(app)}>
                  {t('signInApps.delete', 'Löschen')}
                </Button>
              </Group>
            </Stack>
          </Paper>
        ))}
      </Stack>

      {editing !== null && (
        <AppModal
          open
          app={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(made) => {
            setEditing(null)
            void refresh()
            if (made) setShown(made)
            else notify('success', t('signInApps.saved', 'Gespeichert'))
          }}
        />
      )}
      <CredentialsModal app={shown} discoveryUrl={apps.data?.discoveryUrl ?? ''} onClose={() => setShown(null)} />
      <ConfirmModal
        open={renewing !== null}
        title={t('signInApps.renewTitle', 'Neues Secret erstellen?')}
        body={t(
          'signInApps.renewBody',
          'Das alte Secret gilt sofort nicht mehr. Bis das neue in der Website steht, kann sich niemand anmelden.',
        )}
        onConfirm={() => {
          const app = renewing
          setRenewing(null)
          if (app)
            newClubSignInAppSecret(app.id)
              .then((made) => {
                setShown(made)
                return refresh()
              })
              .catch(fail(t('signInApps.saveFailed', 'Nicht gespeichert')))
        }}
        onClose={() => setRenewing(null)}
      />
      <ConfirmModal
        open={deleting !== null}
        title={t('signInApps.deleteTitle', 'Anmelde-App löschen?')}
        body={t(
          'signInApps.deleteBody',
          'Die Website kann danach niemanden mehr mit Hubra anmelden, und alle Anmeldungen enden.',
        )}
        onConfirm={() => {
          const app = deleting
          setDeleting(null)
          if (app)
            deleteClubSignInApp(app.id)
              .then(refresh)
              .catch(fail(t('signInApps.deleteFailed', 'Löschen fehlgeschlagen')))
        }}
        onClose={() => setDeleting(null)}
      />
    </Paper>
  )
}
