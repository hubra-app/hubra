import { useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Code,
  CopyButton,
  Group,
  Paper,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { useLang, tr } from '@/lang'
import { formatAgo } from '@/format'
import { Modal } from '@/components/ui'
import { useConfirm } from '@/components/useConfirm'
import { SettingsSection } from '@/screens/platform/SettingsSection'
import {
  createOAuthApp,
  deleteOAuthApp,
  editOAuthApp,
  listOAuthApps,
  newOAuthAppSecret,
  type NewOAuthApp,
  type OAuthApp,
} from '@/api/oauthApps'

const KEY = ['oauth-apps']

function errorText(err: unknown): string | undefined {
  return (err as { message?: string } | null)?.message ?? undefined
}

function Copyable({ value, testId }: { value: string; testId?: string }) {
  return (
    <Group gap="xs" wrap="nowrap" align="flex-start">
      <Code block style={{ flex: 1, wordBreak: 'break-all', whiteSpace: 'pre-wrap' }} data-testid={testId}>
        {value}
      </Code>
      <CopyButton value={value}>
        {({ copied, copy }) => (
          <Button size="xs" variant={copied ? 'light' : 'default'} onClick={copy}>
            {copied ? tr('Kopiert', 'Copied') : tr('Kopieren', 'Copy')}
          </Button>
        )}
      </CopyButton>
    </Group>
  )
}

/** The client id and, once, the secret of a new app. */
function SecretModal({ app, onClose }: { app: NewOAuthApp | null; onClose: () => void }) {
  return (
    <Modal
      open={app !== null}
      onClose={onClose}
      title={tr('Zugangsdaten der App', 'App credentials')}
      footer={<Button onClick={onClose}>{tr('Fertig', 'Done')}</Button>}
    >
      {app && (
        <Stack gap="sm">
          <Text size="sm" fw={600}>
            Client ID
          </Text>
          <Copyable value={app.clientId} />
          {app.clientSecret ? (
            <>
              <Alert color="orange" variant="light" title={tr('Nur jetzt sichtbar', 'Shown only now')}>
                {tr(
                  'Hubra speichert nur einen Hash. Gib das Geheimnis jetzt der App; danach lässt es sich nur noch ersetzen.',
                  'Hubra keeps only a hash. Give the secret to the app now; afterwards it can only be replaced.',
                )}
              </Alert>
              <Text size="sm" fw={600}>
                Client Secret
              </Text>
              <Copyable value={app.clientSecret} testId="new-client-secret" />
            </>
          ) : (
            <Text size="xs" c="dimmed">
              {tr(
                'Öffentliche App ohne Geheimnis: sie meldet sich nur mit PKCE an.',
                'Public app without a secret: it signs in with PKCE only.',
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
  app: OAuthApp | null
  onClose: () => void
  onSaved: (made?: NewOAuthApp) => void
}) {
  const { notify } = useAdmin()
  const [name, setName] = useState(app?.name ?? '')
  const [description, setDescription] = useState(app?.description ?? '')
  const [clientUri, setClientUri] = useState(app?.clientUri ?? '')
  const [uris, setUris] = useState((app?.redirectUris ?? []).join('\n'))
  const [mcp, setMcp] = useState(app?.resources.includes('mcp') ?? false)
  const [api, setApi] = useState(app ? app.resources.includes('api') : true)
  const [write, setWrite] = useState(app?.scopes.includes('write') ?? false)
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
      resources: [...(api ? ['api' as const] : []), ...(mcp ? ['mcp' as const] : [])],
      scopes: write ? (['read', 'write'] as ('read' | 'write')[]) : (['read'] as ('read' | 'write')[]),
    }
    try {
      if (app) {
        await editOAuthApp(app.id, body)
        onSaved()
      } else {
        onSaved(await createOAuthApp({ ...body, confidential }))
      }
    } catch (err) {
      notify('error', tr('Nicht gespeichert', 'Not saved'), errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={app ? tr('App bearbeiten', 'Edit app') : tr('Neue App', 'New app')}
      subtitle={tr(
        'Eine App handelt für eine Person, nachdem sie es auf der Anmeldeseite erlaubt hat. Sie kann nie mehr als diese Person.',
        'An app acts for a person after they allowed it on the sign-in page. It can never do more than that person.',
      )}
      onSubmit={submit}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!name.trim() || !uris.trim() || (!api && !mcp)}>
            {app ? tr('Speichern', 'Save') : tr('Erstellen', 'Create')}
          </Button>
        </>
      }
    >
      <TextInput
        label={tr('Name', 'Name')}
        description={tr('So sieht die Person die App beim Erlauben.', 'What the person sees when allowing it.')}
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        maxLength={100}
        required
        data-autofocus
      />
      <Textarea
        label={tr('Beschreibung (optional)', 'Description (optional)')}
        value={description}
        onChange={(e) => setDescription(e.currentTarget.value)}
        maxLength={500}
        autosize
        minRows={2}
      />
      <TextInput
        label={tr('Webseite (optional)', 'Website (optional)')}
        placeholder="https://"
        value={clientUri}
        onChange={(e) => setClientUri(e.currentTarget.value)}
      />
      <Textarea
        label={tr('Rücksprung-Adressen', 'Redirect URIs')}
        description={tr(
          'Eine pro Zeile, genau so, wie die App sie schickt. https, oder http auf localhost (jeder Port).',
          'One per line, exactly as the app sends them. https, or http on localhost (any port).',
        )}
        placeholder="https://app.example/oauth/callback"
        value={uris}
        onChange={(e) => setUris(e.currentTarget.value)}
        autosize
        minRows={2}
        required
      />
      <Stack gap={6}>
        <Text size="sm" fw={500}>
          {tr('Wofür', 'For')}
        </Text>
        <Checkbox
          label={tr('Hubra-API (Skripte, Integrationen)', 'Hubra API (scripts, integrations)')}
          checked={api}
          onChange={(e) => setApi(e.currentTarget.checked)}
        />
        <Checkbox
          label={tr('Claude-Connector (nur lesen)', 'Claude connector (read only)')}
          checked={mcp}
          onChange={(e) => setMcp(e.currentTarget.checked)}
        />
        <Checkbox
          label={tr('Darf auch ändern (nur Hubra-API, nur was die Person darf)', 'May also change (Hubra API only, only what the person may)')}
          checked={write}
          onChange={(e) => setWrite(e.currentTarget.checked)}
        />
        {!app && (
          <Checkbox
            label={tr('Mit Geheimnis (Server-App)', 'With a secret (server app)')}
            description={tr(
              'Aus für Apps im Browser oder auf dem Gerät: sie melden sich nur mit PKCE an.',
              'Off for apps in the browser or on a device: they sign in with PKCE only.',
            )}
            checked={confidential}
            onChange={(e) => setConfidential(e.currentTarget.checked)}
          />
        )}
      </Stack>
    </Modal>
  )
}

/**
 * Access & security › API tokens › Apps: outside apps that may act for a
 * person with their consent (OAuth, docs/oauth.md). Registered apps come
 * from here; Claude registers itself (if allowed below) and can only read
 * through the connector.
 */
export function OAuthApps() {
  const { notify } = useAdmin()
  useLang()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: KEY, queryFn: listOAuthApps })
  const [editing, setEditing] = useState<OAuthApp | 'new' | null>(null)
  const [secret, setSecret] = useState<NewOAuthApp | null>(null)
  const [confirm, confirmDialog] = useConfirm()
  const refresh = () => queryClient.invalidateQueries({ queryKey: KEY })

  const toggle = async (app: OAuthApp) => {
    try {
      await editOAuthApp(app.id, { disabled: !app.disabledAt })
      refresh()
    } catch (err) {
      notify('error', tr('Nicht gespeichert', 'Not saved'), errorText(err))
    }
  }

  const renew = (app: OAuthApp) =>
    confirm({
      title: tr(`Neues Geheimnis für «${app.name}»?`, `New secret for "${app.name}"?`),
      body: tr(
        'Das alte Geheimnis hört sofort auf zu funktionieren. Die App braucht das neue, bevor sie sich wieder anmelden kann.',
        'The old secret stops working at once. The app needs the new one before it can sign in again.',
      ),
      confirmLabel: tr('Ersetzen', 'Replace'),
      run: async () => {
        try {
          setSecret(await newOAuthAppSecret(app.id))
          refresh()
        } catch (err) {
          notify('error', tr('Nicht ersetzt', 'Not replaced'), errorText(err))
        }
      },
    })

  const remove = (app: OAuthApp) =>
    confirm({
      title: tr(`«${app.name}» löschen?`, `Delete "${app.name}"?`),
      body: tr(
        `Alle ${app.activeGrants} Zugänge der App enden sofort.`,
        `All ${app.activeGrants} sign-ins of the app end at once.`,
      ),
      run: async () => {
        try {
          await deleteOAuthApp(app.id)
          notify('success', tr('App gelöscht', 'App deleted'), app.name)
          refresh()
        } catch (err) {
          notify('error', tr('Nicht gelöscht', 'Not deleted'), errorText(err))
        }
      },
    })

  const items = data?.items ?? []
  return (
    <Stack gap={20} maw={1200}>
      <Paper withBorder p="lg">
        <Group justify="space-between" mb={8} align="flex-start">
          <div>
            <Title order={3}>{tr('Apps', 'Apps')}</Title>
            <Text size="xs" c="dimmed" maw={720}>
              {tr(
                'Apps, die mit der Erlaubnis einer Person für sie lesen (oder ändern) dürfen. Die Person wählt den Verein und wie lange, und beendet den Zugang unter Mein Konto › Apps; Vereinsadmins sehen ihn unter Einstellungen › API & Apps.',
                'Apps that may read (or change) for a person with their consent. The person picks the club and for how long, and ends it under My account › Apps; club admins see it under Settings › API & apps.',
              )}
            </Text>
          </div>
          <Button onClick={() => setEditing('new')}>{tr('Neue App', 'New app')}</Button>
        </Group>
        {data && (
          <Text size="xs" c="dimmed" mb={12}>
            {tr('Server-Metadaten', 'Server metadata')}: <Code>{data.metadataUrl}</Code>
            {data.mcpResource && (
              <>
                {' · '}
                {tr('Connector', 'Connector')}: <Code>{data.mcpResource}</Code>
              </>
            )}
          </Text>
        )}
        {isLoading ? (
          <Text size="sm" c="dimmed">
            {tr('Wird geladen …', 'Loading…')}
          </Text>
        ) : items.length === 0 ? (
          <Text size="sm" c="dimmed">
            {tr('Noch keine Apps.', 'No apps yet.')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={860}>
            <Table verticalSpacing="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{tr('App', 'App')}</Table.Th>
                  <Table.Th>{tr('Wofür', 'For')}</Table.Th>
                  <Table.Th>{tr('Zurück zu', 'Returns to')}</Table.Th>
                  <Table.Th>{tr('Zugänge', 'Sign-ins')}</Table.Th>
                  <Table.Th>{tr('Zuletzt benutzt', 'Last used')}</Table.Th>
                  <Table.Th>{tr('Aktiv', 'On')}</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {items.map((a) => (
                  <Table.Tr key={a.id}>
                    <Table.Td>
                      <Group gap={6} wrap="nowrap">
                        <Text size="sm" fw={500}>
                          {a.name}
                        </Text>
                        {a.kind === 'dynamic' && (
                          <Badge size="xs" variant="light" color="yellow">
                            {tr('selbst angemeldet', 'self-registered')}
                          </Badge>
                        )}
                      </Group>
                      <Text size="xs" c="dimmed" ff="monospace" style={{ wordBreak: 'break-all', maxWidth: 240 }}>
                        {a.clientId}
                      </Text>
                    </Table.Td>
                    <Table.Td style={{ whiteSpace: 'nowrap', minWidth: 120 }}>
                      <Group gap={4} wrap="nowrap">
                        {a.resources.map((r) => (
                          <Badge key={r} size="sm" variant="light" color={r === 'mcp' ? 'violet' : 'blue'} style={{ flexShrink: 0, overflow: 'visible' }}>
                            {r === 'mcp' ? 'Claude' : 'API'}
                          </Badge>
                        ))}
                        {a.scopes.includes('write') && (
                          <Badge size="sm" variant="light" color="orange" style={{ flexShrink: 0 }}>
                            {tr('ändern', 'write')}
                          </Badge>
                        )}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">
                        {a.redirectUris
                          .map((u) => {
                            try {
                              return new URL(u).host
                            } catch {
                              return u
                            }
                          })
                          .filter((h, i, all) => all.indexOf(h) === i)
                          .join(', ')}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{a.activeGrants}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{formatAgo(a.lastUsedAt, tr)}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Switch
                        size="xs"
                        checked={!a.disabledAt}
                        onChange={() => void toggle(a)}
                        aria-label={tr('App ein- oder ausschalten', 'Switch the app on or off')}
                      />
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} wrap="nowrap" justify="flex-end">
                        {a.kind === 'registered' && (
                          <>
                            <Button size="compact-xs" variant="subtle" onClick={() => setEditing(a)}>
                              {tr('Bearbeiten', 'Edit')}
                            </Button>
                            {a.confidential && (
                              <Button size="compact-xs" variant="subtle" onClick={() => renew(a)}>
                                {tr('Neues Geheimnis', 'New secret')}
                              </Button>
                            )}
                          </>
                        )}
                        <Button size="compact-xs" variant="subtle" color="red" onClick={() => remove(a)}>
                          {tr('Löschen', 'Delete')}
                        </Button>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Paper>
      <SettingsSection section="oauth" />
      {editing !== null && (
        <AppModal
          open
          app={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(made) => {
            setEditing(null)
            refresh()
            if (made) setSecret(made)
            else notify('success', tr('Gespeichert', 'Saved'))
          }}
        />
      )}
      <SecretModal app={secret} onClose={() => setSecret(null)} />
      {confirmDialog}
    </Stack>
  )
}
