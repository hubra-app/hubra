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
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { useLang, tr } from '@/lang'
import { formatAgo, formatDate } from '@/format'
import { Modal } from '@/components/ui'
import { useConfirm } from '@/components/useConfirm'
import { SettingsSection } from '@/screens/platform/SettingsSection'
import {
  editPlatformToken,
  getAllApiTokens,
  getMyPlatformTokens,
  makePlatformToken,
  revokeAnyApiToken,
  revokeMyPlatformToken,
  rollPlatformToken,
  type ApiToken,
  type NewApiToken,
} from '@/api/apiTokens'

const DEFAULT_SCOPE = 'platform.diagnostics'
const GRACE_HOURS = [0, 1, 24, 168]

function errorText(err: unknown): string | undefined {
  const e = err as { code?: string; message?: string } | null
  if (e?.code === 'MFA_SETUP_FIRST') {
    return tr(
      'Zuerst die Zwei-Faktor-Anmeldung im Konto einschalten (SSO › Konto › Sicherheit).',
      'Turn on two-factor sign-in in your account first (SSO › Account › Security).',
    )
  }
  return e?.message ?? undefined
}

function StatusBadge({ t }: { t: ApiToken }) {
  if (t.active) {
    return (
      <Badge color="green" variant="light">
        {tr('Aktiv', 'Active')}
      </Badge>
    )
  }
  const reason: Record<string, string> = {
    revoked: tr('Widerrufen', 'Revoked'),
    rolled: tr('Ersetzt', 'Replaced'),
    unused: tr('Unbenutzt beendet', 'Ended unused'),
    failed_attempts: tr('Falsche Schlüssel', 'Wrong secrets'),
    account_reset: tr('Konto zurückgesetzt', 'Account reset'),
    replaced: tr('Neu angemeldet', 'Signed in again'),
    app_revoked: tr('Von der App beendet', 'Ended by the app'),
    code_reused: tr('Code kopiert', 'Code reused'),
    refresh_reused: tr('Token kopiert', 'Token reused'),
  }
  const ended = t.revokedAt ? (reason[t.revokedReason ?? ''] ?? tr('Beendet', 'Ended')) : tr('Abgelaufen', 'Expired')
  return (
    <Badge color="gray" variant="light">
      {ended}
    </Badge>
  )
}

/** The secret, once, with the Claude Code command that uses it. */
function SecretPanel({ token, mcpUrl }: { token: NewApiToken; mcpUrl: string }) {
  const command = mcpUrl
    ? `claude mcp add --transport http hubra ${mcpUrl}/mcp --header "Authorization: Bearer ${token.token}"`
    : ''
  return (
    <Stack gap="sm">
      <Alert color="orange" variant="light" title={tr('Nur jetzt sichtbar', 'Shown only now')}>
        {tr(
          'Hubra speichert nur einen Hash. Kopiere das Token jetzt; danach lässt es sich nur noch ersetzen.',
          'Hubra keeps only a hash. Copy the token now; afterwards it can only be replaced.',
        )}
      </Alert>
      <Group gap="xs" wrap="nowrap" align="flex-start">
        <Code block style={{ flex: 1, wordBreak: 'break-all', whiteSpace: 'pre-wrap' }} data-testid="new-token">
          {token.token}
        </Code>
        <CopyButton value={token.token}>
          {({ copied, copy }) => (
            <Button size="xs" variant={copied ? 'light' : 'default'} onClick={copy}>
              {copied ? tr('Kopiert', 'Copied') : tr('Kopieren', 'Copy')}
            </Button>
          )}
        </CopyButton>
      </Group>
      {token.previous && (
        <Text size="xs" c="dimmed">
          {tr(
            `Das alte Token gilt noch bis ${token.previous.expiresAt ? formatDate(token.previous.expiresAt) : '–'}.`,
            `The old token keeps working until ${token.previous.expiresAt ? formatDate(token.previous.expiresAt) : '–'}.`,
          )}
        </Text>
      )}
      {command && (
        <>
          <Text size="sm" fw={600}>
            {tr('Mit Claude Code verbinden', 'Connect Claude Code')}
          </Text>
          <Group gap="xs" wrap="nowrap" align="flex-start">
            <Code block style={{ flex: 1, wordBreak: 'break-all', whiteSpace: 'pre-wrap' }}>
              {command}
            </Code>
            <CopyButton value={command}>
              {({ copied, copy }) => (
                <Button size="xs" variant={copied ? 'light' : 'default'} onClick={copy}>
                  {copied ? tr('Kopiert', 'Copied') : tr('Kopieren', 'Copy')}
                </Button>
              )}
            </CopyButton>
          </Group>
        </>
      )}
    </Stack>
  )
}

function ScopePicker({
  grantable,
  value,
  onChange,
}: {
  grantable: string[]
  value: string[]
  onChange: (v: string[]) => void
}) {
  return (
    <Checkbox.Group label={tr('Berechtigungen', 'Permissions')} value={value} onChange={onChange}>
      <Stack gap={6} mt={6}>
        {grantable.map((key) => (
          <Checkbox key={key} value={key} label={<Code>{key}</Code>} />
        ))}
      </Stack>
    </Checkbox.Group>
  )
}

function MakeTokenModal({
  open,
  onClose,
  grantable,
  maxDays,
  onMade,
}: {
  open: boolean
  onClose: () => void
  grantable: string[]
  maxDays: number
  onMade: (t: NewApiToken) => void
}) {
  const { notify } = useAdmin()
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState<string[]>([DEFAULT_SCOPE])
  const [days, setDays] = useState(String(maxDays))
  const [ips, setIps] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event?: FormEvent) => {
    // The dialog is a form: without this the browser reloads the page and
    // a new secret would be lost before it is shown.
    event?.preventDefault()
    setBusy(true)
    try {
      const allowedIps = ips
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean)
      const made = await makePlatformToken({
        name: name.trim(),
        scopes,
        days: Number(days),
        ...(allowedIps.length ? { allowedIps } : {}),
      })
      setName('')
      setScopes([DEFAULT_SCOPE])
      setIps('')
      onMade(made)
    } catch (err) {
      notify('error', tr('Token nicht erstellt', 'Token not made'), errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={tr('Neues Plattform-Token', 'New platform token')}
      subtitle={tr(
        'Nur lesend, höchstens 30 Tage. Es kann nie mehr als du.',
        'Read-only, 30 days at most. It can never do more than you.',
      )}
      onSubmit={submit}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!name.trim() || scopes.length === 0}>
            {tr('Erstellen', 'Create')}
          </Button>
        </>
      }
    >
      <TextInput
        label={tr('Name', 'Name')}
        placeholder={tr('z. B. Claude Diagnose', 'e.g. Claude diagnostics')}
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        maxLength={100}
        required
        data-autofocus
      />
      <ScopePicker grantable={grantable} value={scopes} onChange={setScopes} />
      <Select
        label={tr('Gültig für', 'Valid for')}
        data={[7, 30]
          .filter((d) => d <= maxDays)
          .map((d) => ({ value: String(d), label: tr(`${d} Tage`, `${d} days`) }))}
        value={days}
        onChange={(v) => v && setDays(v)}
        allowDeselect={false}
      />
      <Textarea
        label={tr('Nur von diesen Adressen (optional)', 'Only from these addresses (optional)')}
        description={tr(
          'IP-Adressen oder Netze (CIDR), durch Komma oder Zeile getrennt. Über den Claude-Connector zählt die Adresse, von der aus Claude verbindet.',
          'IP addresses or networks (CIDR), separated by commas or lines. Through the Claude connector, the address Claude connects from counts.',
        )}
        placeholder="203.0.113.7, 2001:db8::/48"
        value={ips}
        onChange={(e) => setIps(e.currentTarget.value)}
        autosize
        minRows={1}
      />
    </Modal>
  )
}

function EditTokenModal({
  token,
  grantable,
  onClose,
  onSaved,
}: {
  token: ApiToken | null
  grantable: string[]
  onClose: () => void
  onSaved: () => void
}) {
  const { notify } = useAdmin()
  const [name, setName] = useState(token?.name ?? '')
  const [scopes, setScopes] = useState<string[]>(token?.scopes ?? [])
  const [busy, setBusy] = useState(false)
  if (!token) return null
  const options = Array.from(new Set([...grantable, ...token.scopes])).sort()

  const submit = async (event?: FormEvent) => {
    // The dialog is a form: without this the browser reloads the page and
    // a new secret would be lost before it is shown.
    event?.preventDefault()
    setBusy(true)
    try {
      await editPlatformToken(token.id, { name: name.trim(), scopes })
      notify('success', tr('Token gespeichert', 'Token saved'), name.trim())
      onSaved()
    } catch (err) {
      notify('error', tr('Nicht gespeichert', 'Not saved'), errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={tr('Token bearbeiten', 'Edit token')}
      subtitle={tr(
        'Weniger Berechtigungen gehen sofort; eine neue braucht dein Passwort.',
        'Fewer permissions apply at once; adding one asks for your password.',
      )}
      onSubmit={submit}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!name.trim() || scopes.length === 0}>
            {tr('Speichern', 'Save')}
          </Button>
        </>
      }
    >
      <TextInput
        label={tr('Name', 'Name')}
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        maxLength={100}
        required
      />
      <ScopePicker grantable={options} value={scopes} onChange={setScopes} />
    </Modal>
  )
}

function RollTokenModal({
  token,
  onClose,
  onRolled,
}: {
  token: ApiToken | null
  onClose: () => void
  onRolled: (t: NewApiToken) => void
}) {
  const { notify } = useAdmin()
  const [grace, setGrace] = useState('24')
  const [busy, setBusy] = useState(false)
  if (!token) return null
  const label = (h: number) =>
    h === 0
      ? tr('Sofort beenden', 'End it now')
      : h === 168
        ? tr('1 Woche', '1 week')
        : tr(`${h} Std.`, `${h} h`)

  const submit = async (event?: FormEvent) => {
    // The dialog is a form: without this the browser reloads the page and
    // a new secret would be lost before it is shown.
    event?.preventDefault()
    setBusy(true)
    try {
      onRolled(await rollPlatformToken(token.id, { graceHours: Number(grace) }))
    } catch (err) {
      notify('error', tr('Nicht ersetzt', 'Not replaced'), errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={tr('Neuen Schlüssel ausgeben', 'Issue a new secret')}
      subtitle={token.name}
      onSubmit={submit}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {tr('Ersetzen', 'Replace')}
          </Button>
        </>
      }
    >
      <Text size="sm">
        {tr(
          'Das Token bekommt einen neuen Schlüssel mit denselben Berechtigungen. Der alte gilt noch so lange, bis deine Skripte umgestellt sind:',
          'The token gets a new secret with the same permissions. The old one keeps working until your scripts have switched:',
        )}
      </Text>
      <SegmentedControl
        value={grace}
        onChange={setGrace}
        data={GRACE_HOURS.map((h) => ({ value: String(h), label: label(h) }))}
      />
    </Modal>
  )
}

/** Access & security › API tokens › Mine: my read-only platform tokens. */
export function MyPlatformTokens() {
  const { notify } = useAdmin()
  useLang()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['platform-api-tokens'], queryFn: getMyPlatformTokens })
  const [making, setMaking] = useState(false)
  const [editing, setEditing] = useState<ApiToken | null>(null)
  const [rolling, setRolling] = useState<ApiToken | null>(null)
  const [shown, setShown] = useState<NewApiToken | null>(null)
  const [confirm, confirmDialog] = useConfirm()
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['platform-api-tokens'] })

  if (isLoading || !data) {
    return (
      <Text size="sm" c="dimmed">
        {tr('Wird geladen …', 'Loading…')}
      </Text>
    )
  }
  const active = data.items.filter((t) => t.active)
  const ended = data.items.filter((t) => !t.active)

  const revoke = (t: ApiToken) =>
    confirm({
      title: tr(`«${t.name}» widerrufen?`, `Revoke "${t.name}"?`),
      body: tr(
        'Alles, was dieses Token nutzt, hört sofort auf zu funktionieren.',
        'Everything that uses this token stops working at once.',
      ),
      confirmLabel: tr('Widerrufen', 'Revoke'),
      run: async () => {
        try {
          await revokeMyPlatformToken(t.id)
          notify('success', tr('Token widerrufen', 'Token revoked'), t.name)
          refresh()
        } catch (err) {
          notify('error', tr('Nicht widerrufen', 'Not revoked'), errorText(err))
        }
      },
    })

  const row = (t: ApiToken) => (
    <Table.Tr key={t.id}>
      <Table.Td>
        <Text size="sm" fw={500}>
          {t.name}
        </Text>
        <Text size="xs" c="dimmed" ff="monospace">
          {t.prefix}
        </Text>
      </Table.Td>
      <Table.Td>
        <Group gap={4}>
          {t.scopes.map((s) => (
            <Badge key={s} size="sm" variant="outline" tt="none">
              {s}
            </Badge>
          ))}
        </Group>
      </Table.Td>
      <Table.Td>
        <Text size="sm">{formatAgo(t.lastUsedAt, tr)}</Text>
        {t.lastUsedIp && (
          <Text size="xs" c="dimmed">
            {t.lastUsedIp}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {t.active ? (
          <Text size="sm">{t.expiresAt ? formatDate(t.expiresAt) : '–'}</Text>
        ) : (
          <StatusBadge t={t} />
        )}
      </Table.Td>
      <Table.Td>
        {t.active && (
          <Group gap={4} justify="flex-end" wrap="nowrap">
            <Button size="compact-xs" variant="subtle" onClick={() => setEditing(t)}>
              {tr('Bearbeiten', 'Edit')}
            </Button>
            <Button size="compact-xs" variant="subtle" onClick={() => setRolling(t)}>
              {tr('Ersetzen', 'Replace')}
            </Button>
            <Button size="compact-xs" variant="subtle" color="red" onClick={() => revoke(t)}>
              {tr('Widerrufen', 'Revoke')}
            </Button>
          </Group>
        )}
      </Table.Td>
    </Table.Tr>
  )

  const head = (
    <Table.Thead>
      <Table.Tr>
        <Table.Th>{tr('Token', 'Token')}</Table.Th>
        <Table.Th>{tr('Berechtigungen', 'Permissions')}</Table.Th>
        <Table.Th>{tr('Zuletzt benutzt', 'Last used')}</Table.Th>
        <Table.Th>{tr('Gültig bis', 'Valid until')}</Table.Th>
        <Table.Th />
      </Table.Tr>
    </Table.Thead>
  )

  return (
    <Stack gap={20} maw={1040}>
      <Paper withBorder p="lg">
        <Group justify="space-between" mb={4}>
          <Title order={3}>{tr('Meine Plattform-Tokens', 'My platform tokens')}</Title>
          <Button onClick={() => setMaking(true)} disabled={active.length >= 5}>
            {tr('Neues Token', 'New token')}
          </Button>
        </Group>
        <Text size="xs" c="dimmed" mb={12}>
          {tr(
            'Für Skripte und den Claude-Connector: lesen die Diagnose der Plattform (Leistung, Fehler, Jobs, Warnungen), nie einen Verein, nie schreibend. Erstellen braucht Zwei-Faktor und dein Passwort. Ein Token endet nach 60 Tagen ohne Nutzung, bei einem Passwort-Reset und nach 10 falschen Schlüsseln.',
            'For scripts and the Claude connector: they read the platform diagnostics (performance, errors, jobs, alerts), never a club, never writing. Making one needs two-factor and your password. A token ends after 60 days unused, on a password reset and after 10 wrong secrets.',
          )}
        </Text>
        {active.length === 0 ? (
          <Text size="sm" c="dimmed">
            {tr('Noch keine Tokens.', 'No tokens yet.')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={720}>
            <Table verticalSpacing="xs">
              {head}
              <Table.Tbody>{active.map(row)}</Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Paper>

      <Paper withBorder p="lg">
        <Title order={3} mb={4}>
          {tr('Claude-Connector', 'Claude connector')}
        </Title>
        {data.mcpUrl ? (
          <>
            <Text size="xs" c="dimmed" mb={12}>
              {tr(
                'Der Connector liest die Hubra-API mit deinem Token und hat sonst keinen Zugriff. Claude sieht damit nur, was das Token darf. In Claude Code:',
                'The connector reads the Hubra API with your token and has no other access, so Claude only sees what the token may. In Claude Code:',
              )}
            </Text>
            <Code block style={{ wordBreak: 'break-all', whiteSpace: 'pre-wrap' }}>
              {`claude mcp add --transport http hubra ${data.mcpUrl}/mcp --header "Authorization: Bearer hbr_plat_…"`}
            </Code>
          </>
        ) : (
          <Text size="sm" c="dimmed">
            {tr(
              'Noch keine Adresse gesetzt (Einstellung unten). Der Connector ist das Image mcp, siehe docs/mcp.md.',
              'No address set yet (setting below). The connector is the mcp image, see docs/mcp.md.',
            )}
          </Text>
        )}
      </Paper>

      {ended.length > 0 && (
        <Paper withBorder p="lg">
          <Title order={4} mb={8}>
            {tr('Beendet', 'Ended')}
          </Title>
          <Table.ScrollContainer minWidth={720}>
            <Table verticalSpacing="xs">
              {head}
              <Table.Tbody>{ended.slice(0, 20).map(row)}</Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Paper>
      )}

      <MakeTokenModal
        open={making}
        onClose={() => setMaking(false)}
        grantable={data.grantable}
        maxDays={data.maxDays}
        onMade={(t) => {
          setMaking(false)
          setShown(t)
          refresh()
        }}
      />
      {editing && (
        <EditTokenModal
          key={editing.id}
          token={editing}
          grantable={data.grantable}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            refresh()
          }}
        />
      )}
      {rolling && (
        <RollTokenModal
          key={rolling.id}
          token={rolling}
          onClose={() => setRolling(null)}
          onRolled={(t) => {
            setRolling(null)
            setShown(t)
            refresh()
          }}
        />
      )}
      <Modal
        open={shown !== null}
        onClose={() => setShown(null)}
        title={shown?.previous ? tr('Neuer Schlüssel', 'New secret') : tr('Token erstellt', 'Token created')}
        subtitle={shown?.name}
        wide
        footer={<Button onClick={() => setShown(null)}>{tr('Fertig', 'Done')}</Button>}
      >
        {shown && <SecretPanel token={shown} mcpUrl={data.mcpUrl} />}
      </Modal>
      {confirmDialog}
    </Stack>
  )
}

/** My tokens, plus the connector address for those who may set it. */
export function PlatformTokensPage() {
  const { hasGlobalPermission } = useAdmin()
  return (
    <Stack gap={20}>
      <MyPlatformTokens />
      {hasGlobalPermission('platform.settings') && <SettingsSection section="mcp" />}
    </Stack>
  )
}

const KIND_LABEL = (t: ApiToken) =>
  t.appId
    ? tr('App', 'App')
    : t.kind === 'platform'
      ? tr('Plattform', 'Platform')
      : t.kind === 'club'
        ? tr('Verein', 'Club')
        : tr('Persönlich', 'Personal')

/** Access & security › API tokens › All: every token, for platform admins. */
export function AllApiTokens() {
  const { notify } = useAdmin()
  useLang()
  const queryClient = useQueryClient()
  const { data = [], isLoading } = useQuery({ queryKey: ['all-api-tokens'], queryFn: getAllApiTokens })
  const [show, setShow] = useState<'active' | 'all'>('active')
  const [confirm, confirmDialog] = useConfirm()
  const rows = show === 'active' ? data.filter((t) => t.active) : data

  const revoke = (t: ApiToken) =>
    confirm({
      title: tr(`«${t.name}» widerrufen?`, `Revoke "${t.name}"?`),
      body: tr(
        `Das Token von ${t.createdByName} hört sofort auf zu funktionieren. Es steht im Audit-Log.`,
        `${t.createdByName}'s token stops working at once. It goes into the audit log.`,
      ),
      confirmLabel: tr('Widerrufen', 'Revoke'),
      run: async () => {
        try {
          await revokeAnyApiToken(t.id)
          notify('success', tr('Token widerrufen', 'Token revoked'), t.name)
          queryClient.invalidateQueries({ queryKey: ['all-api-tokens'] })
        } catch (err) {
          notify('error', tr('Nicht widerrufen', 'Not revoked'), errorText(err))
        }
      },
    })

  return (
    <Paper withBorder p="lg" maw={1200}>
      <Group justify="space-between" mb={12}>
        <Text size="xs" c="dimmed" maw={720}>
          {tr(
            'Alle Tokens aller Vereine und der Plattform, neueste zuerst. Geheimnisse sieht hier niemand; widerrufen geht jedes.',
            'Every token of every club and of the platform, newest first. Nobody sees secrets here; any one can be revoked.',
          )}
        </Text>
        <SegmentedControl
          size="xs"
          value={show}
          onChange={(v) => setShow(v as 'active' | 'all')}
          data={[
            { value: 'active', label: tr('Aktive', 'Active') },
            { value: 'all', label: tr('Alle', 'All') },
          ]}
        />
      </Group>
      {isLoading ? (
        <Text size="sm" c="dimmed">
          {tr('Wird geladen …', 'Loading…')}
        </Text>
      ) : rows.length === 0 ? (
        <Text size="sm" c="dimmed">
          {tr('Keine Tokens.', 'No tokens.')}
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={860}>
          <Table verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Token', 'Token')}</Table.Th>
                <Table.Th>{tr('Art', 'Kind')}</Table.Th>
                <Table.Th>{tr('Verein', 'Club')}</Table.Th>
                <Table.Th>{tr('Von', 'By')}</Table.Th>
                <Table.Th>{tr('Zuletzt benutzt', 'Last used')}</Table.Th>
                <Table.Th>{tr('Status', 'Status')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((t) => (
                <Table.Tr key={t.id}>
                  <Table.Td>
                    <Text size="sm" fw={500}>
                      {t.name}
                    </Text>
                    <Text size="xs" c="dimmed" ff="monospace">
                      {t.prefix}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" variant="light" color={t.kind === 'platform' ? 'violet' : 'blue'}>
                      {KIND_LABEL(t)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{t.club?.name ?? '–'}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{t.createdByName}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{formatAgo(t.lastUsedAt, tr)}</Text>
                    <Text size="xs" c="dimmed">
                      {tr(`${t.useCount} Aufrufe`, `${t.useCount} calls`)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {t.active ? (
                      <Text size="sm">
                        {tr('bis', 'until')} {t.expiresAt ? formatDate(t.expiresAt) : '–'}
                      </Text>
                    ) : (
                      <StatusBadge t={t} />
                    )}
                  </Table.Td>
                  <Table.Td>
                    {t.active && (
                      <Button size="compact-xs" variant="subtle" color="red" onClick={() => revoke(t)}>
                        {tr('Widerrufen', 'Revoke')}
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {confirmDialog}
    </Paper>
  )
}
