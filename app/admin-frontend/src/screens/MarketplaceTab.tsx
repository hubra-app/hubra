import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Code,
  FileButton,
  Group,
  Loader,
  Menu,
  Modal,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  TextInput,
  ThemeIcon,
} from '@mantine/core'
import {
  IconAlertTriangle,
  IconArrowUp,
  IconBox,
  IconBrandDiscord,
  IconCircleCheck,
  IconDots,
  IconDownload,
  IconMail,
  IconMessages,
  IconPuzzle,
  IconRefresh,
  IconSearch,
  IconUpload,
  IconWallet,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import {
  addRepository,
  addTrustedKey,
  checkUpdates,
  confirmStaged,
  deleteRepository,
  deleteTrustedKey,
  discardStaged,
  getMarketplace,
  getPluginStatus,
  holdPlugin,
  installPlugin,
  listRepositories,
  listTrustedKeys,
  previewRepository,
  rollbackPlugin,
  setRepositoryEnabled,
  setUpdateMode,
  uninstallPlugin,
  uploadPlugin,
  type MarketplacePlugin,
  type PluginChange,
  type StagedPlugin,
  type UpdateMode,
  type KeyPurpose,
  type KeyRef,
  type RepositoryPreview,
} from '@/api/plugins'
import { tr } from '@/lang'
import { EmptyState } from '@/components/ui'
import { useConfirm } from '@/components/useConfirm'
import { PLUGIN_DE } from '@/moduleLabels'

const TRUST: Record<string, { color: string; label: () => string }> = {
  bundled: { color: 'green', label: () => tr('Mit Hubra geliefert', 'Shipped with Hubra') },
  official: { color: 'green', label: () => tr('Offiziell', 'Official') },
  community: { color: 'acc', label: () => tr('Community', 'Community') },
  unsigned: { color: 'orange', label: () => tr('Nicht signiert', 'Unsigned') },
  invalid: { color: 'red', label: () => tr('Ungültige Signatur', 'Invalid signature') },
}

// Extension areas a plugin lists under uses: (docs/plugins.md).
const AREAS: Record<string, [string, string]> = {
  routes: ['Schnittstellen', 'API routes'],
  public: ['öffentliche Seiten', 'public routes'],
  events: ['Ereignisse', 'events'],
  jobs: ['Hintergrundjobs', 'background jobs'],
  processes: ['eigene Prozesse', 'own processes'],
  tables: ['eigene Tabellen', 'own tables'],
  settings: ['Einstellungen', 'settings'],
  apps: ['verbundene Apps', 'connected apps'],
  nav: ['Navigation', 'navigation'],
  frontend: ['Seiten in der Vereins-App', 'club app pages'],
  mail: ['Mails', 'mail'],
  discord: ['Discord', 'Discord'],
}

function usesText(uses: string[] | null | undefined) {
  if (uses == null) return tr('nicht angegeben', 'not declared')
  if (uses.length === 0) return tr('nichts', 'nothing')
  return uses.map((a) => (AREAS[a] ? tr(...AREAS[a]) : a)).join(', ')
}

function dependsText(depends: Record<string, string>) {
  return Object.entries(depends)
    .map(([id, range]) => (range ? `${id} ${range}` : id))
    .join(', ')
}

function TrustBadge({ status }: { status: string }) {
  const t = TRUST[status]
  if (!t) return null
  return (
    <Badge size="xs" variant="light" color={t.color}>
      {t.label()}
    </Badge>
  )
}

const errorText = (err: unknown) => (err instanceof Error ? err.message : String(err))

/**
 * Plugins for the whole platform: install, update, roll back and remove
 * them, and manage where they come from.  A plugin runs with full access to
 * every club, so only platform managers see this.
 */
export function MarketplaceTab() {
  const [view, setView] = useState('plugins')
  return (
    <Stack gap="md">
      <SegmentedControl
        w="fit-content"
        value={view}
        onChange={setView}
        data={[
          { value: 'plugins', label: tr('Plugins', 'Plugins') },
          { value: 'repositories', label: tr('Quellen', 'Repositories') },
          { value: 'keys', label: tr('Signaturschlüssel', 'Signing keys') },
        ]}
      />
      {view === 'plugins' && <PluginsView />}
      {view === 'repositories' && <RepositoriesView />}
      {view === 'keys' && <KeysView />}
    </Stack>
  )
}

// ── Plugins ─────────────────────────────────────────────────────────────────

/** An icon per kind of plugin, from its tags. */
function PluginIcon({ p }: { p: MarketplacePlugin }) {
  const tags = new Set(p.tags)
  const Icon = p.id.includes('discord')
    ? IconBrandDiscord
    : tags.has('mail')
      ? IconMail
      : tags.has('finance')
        ? IconWallet
        : tags.has('inventory')
          ? IconBox
          : tags.has('communication')
            ? IconMessages
            : IconPuzzle
  return (
    <ThemeIcon size={52} radius="md" variant="light" color={p.installed ? 'acc' : 'gray'} aria-hidden>
      <Icon size={28} stroke={1.6} />
    </ThemeIcon>
  )
}

/** Installed with an update first, then installed, then the rest; by name. */
function rank(p: MarketplacePlugin) {
  if (p.installed && (p.update || p.withdrawn || p.error)) return 0
  if (p.installed) return 1
  return 2
}

function PluginsView() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [details, setDetails] = useState<MarketplacePlugin | null>(null)
  const [staged, setStaged] = useState<StagedPlugin | null>(null)
  const [removing, setRemoving] = useState<MarketplacePlugin | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  // Generation every server has to reach before a change is live.
  const [waitFor, setWaitFor] = useState<number | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['marketplace'],
    queryFn: () => getMarketplace(),
  })

  // Poll until the server answering has loaded the change.
  useQuery({
    queryKey: ['plugin-status', waitFor],
    queryFn: async () => {
      const status = await getPluginStatus()
      if (waitFor !== null && status.generation >= waitFor) {
        setWaitFor(null)
        notify('success', tr('Plugins neu geladen', 'Plugins reloaded'), tr('Die Änderung ist aktiv.', 'The change is live.'))
        queryClient.invalidateQueries({ queryKey: ['marketplace'] })
      }
      return status
    },
    enabled: waitFor !== null,
    refetchInterval: 3000,
  })

  const changed = (out: PluginChange, what: string) => {
    notify('success', what, `${out.id} ${out.version}`)
    setWaitFor((w) => Math.max(w ?? 0, out.generation))
    queryClient.invalidateQueries({ queryKey: ['marketplace'] })
  }

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key)
    try {
      await fn()
    } catch (err) {
      notify('error', tr('Plugins', 'Plugins'), errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const install = (p: MarketplacePlugin, version?: string) =>
    run(p.id, async () => {
      // An update names the version shown on the card, so the server
      // installs exactly that one (or says it can't) instead of whatever its
      // copy of the index calls newest.
      const target = version ?? (p.update ? p.repoVersion : undefined)
      const fromRepo = Boolean(target) || !p.bundled
      const out = await installPlugin(p.id, {
        version: target,
        repositoryId: fromRepo ? p.repositoryId : undefined,
      })
      if (out.installed) changed(out.installed, tr('Installiert', 'Installed'))
      if (out.staged) setStaged(out.staged)
    })

  const upload = (file: File | null) =>
    file &&
    run('upload', async () => {
      setStaged(await uploadPlugin(file))
    })

  const all = (data?.plugins ?? []).map((p) => {
    const de = PLUGIN_DE[p.id]
    return de ? { ...p, name: tr(de[0], p.name), description: tr(de[1], p.description) } : p
  })
  const plugins = all
    .filter((p) => {
      if (filter === 'installed' && !p.installed) return false
      if (filter === 'available' && p.installed) return false
      if (filter === 'updates' && !p.update && !p.withdrawn) return false
      const q = search.trim().toLowerCase()
      return !q || `${p.name} ${p.id} ${p.description} ${p.tags.join(' ')}`.toLowerCase().includes(q)
    })
    .sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
  const installedCount = all.filter((p) => p.installed).length
  const updateCount = all.filter((p) => p.update).length
  const installed = plugins.filter((p) => p.installed)
  const available = plugins.filter((p) => !p.installed)

  const card = (p: MarketplacePlugin) => (
    <PluginCard
      key={p.id}
      p={p}
      busy={busy === p.id}
      reloading={waitFor !== null}
      onDetails={() => setDetails(p)}
      onInstall={() => install(p)}
      onRollback={() => run(p.id, async () => changed(await rollbackPlugin(p.id), tr('Zurückgesetzt', 'Rolled back')))}
      onHold={(version) =>
        run(p.id, async () => {
          await holdPlugin(p.id, version)
          await queryClient.invalidateQueries({ queryKey: ['marketplace'] })
        })
      }
      onRemove={() => setRemoving(p)}
    />
  )
  const grid = (list: MarketplacePlugin[]) => (
    <SimpleGrid cols={{ base: 1, sm: 2, xl: 3 }} spacing="md" verticalSpacing="md">
      {list.map(card)}
    </SimpleGrid>
  )

  return (
    <Stack gap="lg">
      {waitFor !== null && (
        <Alert color="acc" variant="light" icon={<Loader size={16} />}>
          {tr('Die Server laden die Änderung. Das dauert bis zu einer Minute.', 'Servers are loading the change. This takes up to a minute.')}
        </Alert>
      )}
      {data?.errors.map((e) => (
        <Alert key={e} color="orange" variant="light" icon={<IconAlertTriangle size={16} />}>
          {e}
        </Alert>
      ))}

      <Paper withBorder p="md">
        <Stack gap="sm">
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Group gap="lg">
              <Stat label={tr('Installiert', 'Installed')} value={installedCount} />
              <Stat label={tr('Updates', 'Updates')} value={updateCount} highlight={updateCount > 0} />
              <Stat label={tr('Im Katalog', 'In the catalogue')} value={all.length} />
            </Group>
            <Group gap="sm" wrap="wrap">
              <Select
                w={220}
                aria-label={tr('Updates', 'Updates')}
                value={data?.updateMode ?? 'notify'}
                onChange={(v) =>
                  v &&
                  run('mode', async () => {
                    await setUpdateMode(v as UpdateMode)
                    await queryClient.invalidateQueries({ queryKey: ['marketplace'] })
                  })
                }
                data={[
                  { value: 'notify', label: tr('Updates: nur melden', 'Updates: tell me') },
                  { value: 'official', label: tr('Updates: offizielle installieren', 'Updates: install official') },
                  { value: 'off', label: tr('Updates: nicht prüfen', 'Updates: don’t check') },
                ]}
              />
              <Button
                variant="default"
                leftSection={<IconRefresh size={16} />}
                loading={busy === 'check'}
                onClick={() =>
                  run('check', async () => {
                    await checkUpdates()
                    await queryClient.invalidateQueries({ queryKey: ['marketplace'] })
                  })
                }
              >
                {tr('Nach Updates suchen', 'Check for updates')}
              </Button>
              <FileButton onChange={upload} accept=".zip,application/zip">
                {(props) => (
                  <Button {...props} variant="default" leftSection={<IconUpload size={16} />} loading={busy === 'upload'}>
                    {tr('Plugin hochladen', 'Upload plugin')}
                  </Button>
                )}
              </FileButton>
            </Group>
          </Group>
          <Group gap="sm" wrap="wrap">
            <TextInput
              style={{ flex: '1 1 220px' }}
              leftSection={<IconSearch size={16} />}
              placeholder={tr('Plugins suchen …', 'Search plugins…')}
              value={search}
              onChange={(e) => setSearch(e.currentTarget.value)}
            />
            <SegmentedControl
              value={filter}
              onChange={setFilter}
              data={[
                { value: 'all', label: tr('Alle', 'All') },
                { value: 'installed', label: tr('Installiert', 'Installed') },
                { value: 'available', label: tr('Verfügbar', 'Available') },
                { value: 'updates', label: updateCount ? `${tr('Updates', 'Updates')} (${updateCount})` : tr('Updates', 'Updates') },
              ]}
            />
          </Group>
        </Stack>
      </Paper>

      {isLoading ? (
        <Group gap="sm" p="lg">
          <Loader size="sm" />
          <Text size="sm" c="dimmed">
            {tr('Katalog wird geladen …', 'Loading the catalogue…')}
          </Text>
        </Group>
      ) : error ? (
        <Alert color="red" variant="light">
          {errorText(error)}
        </Alert>
      ) : plugins.length === 0 ? (
        <Paper withBorder>
          <EmptyState title={tr('Keine passenden Plugins.', 'No plugins match.')} />
        </Paper>
      ) : filter === 'all' ? (
        <>
          {installed.length > 0 && (
            <Stack gap="sm">
              <SectionTitle title={tr('Installiert', 'Installed')} count={installed.length} />
              {grid(installed)}
            </Stack>
          )}
          {available.length > 0 && (
            <Stack gap="sm">
              <SectionTitle title={tr('Verfügbar', 'Available')} count={available.length} />
              {grid(available)}
            </Stack>
          )}
        </>
      ) : (
        grid(plugins)
      )}

      {details && (
        <DetailsModal
          p={details}
          onClose={() => setDetails(null)}
          onInstall={(version) => {
            setDetails(null)
            install(details, version)
          }}
        />
      )}
      {staged && (
        <StagedModal
          s={staged}
          onClose={() => setStaged(null)}
          onInstalled={(out) => {
            setStaged(null)
            changed(out, tr('Installiert', 'Installed'))
          }}
        />
      )}
      {removing && (
        <UninstallModal
          p={removing}
          onClose={() => setRemoving(null)}
          onRemoved={(out) => {
            setRemoving(null)
            changed(out, tr('Entfernt', 'Removed'))
          }}
        />
      )}
    </Stack>
  )
}

function Stat({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <Stack gap={0}>
      <Text size="xl" fw={700} lh={1.1} c={highlight ? 'gold.8' : undefined}>
        {value}
      </Text>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
    </Stack>
  )
}

function SectionTitle({ title, count }: { title: string; count: number }) {
  return (
    <Group gap={8}>
      <Text fw={700} size="sm" tt="uppercase" c="dimmed" style={{ letterSpacing: 0.4 }}>
        {title}
      </Text>
      <Badge size="sm" variant="light" color="gray" circle>
        {count}
      </Badge>
    </Group>
  )
}

function PluginCard({
  p,
  busy,
  reloading,
  onDetails,
  onInstall,
  onRollback,
  onHold,
  onRemove,
}: {
  p: MarketplacePlugin
  busy: boolean
  reloading: boolean
  onDetails: () => void
  onInstall: () => void
  onRollback: () => void
  onHold: (version: string | null) => void
  onRemove: () => void
}) {
  const offered = p.repoVersion ?? p.version
  const pending = p.pendingReload
  return (
    <Card withBorder radius="md" padding="lg" style={{ display: 'flex', flexDirection: 'column' }} data-plugin={p.id}>
      <Group align="flex-start" wrap="nowrap" gap="md">
        <PluginIcon p={p} />
        <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
          <Anchor component="button" ta="left" fw={700} size="lg" c="var(--mantine-color-text)" onClick={onDetails} lineClamp={1}>
            {p.name}
          </Anchor>
          <Text size="xs" c="dimmed" lineClamp={1}>
            {p.installed ? p.installedVersion : offered}
            {p.author ? ` · ${p.author}` : ''}
          </Text>
          <Group gap={6} mt={4}>
            <TrustBadge status={p.trust?.status || (p.officialSigned ? 'official' : '')} />
            {p.tags.slice(0, 3).map((t) => (
              <Badge key={t} size="xs" variant="outline" color="gray">
                {t}
              </Badge>
            ))}
          </Group>
        </Stack>
        {p.installed && (
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" aria-label={tr(`Mehr zu ${p.name}`, `More for ${p.name}`)}>
                <IconDots size={18} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item onClick={onDetails}>{tr('Details und Versionen', 'Details and versions')}</Menu.Item>
              {p.previous && <Menu.Item onClick={onRollback}>{tr('Zurück auf', 'Roll back to')} {p.previous}</Menu.Item>}
              {p.repositoryId !== null &&
                (p.held ? (
                  <Menu.Item onClick={() => onHold(null)}>{tr('Updates wieder erlauben', 'Allow updates again')}</Menu.Item>
                ) : (
                  <Menu.Item onClick={() => onHold(p.installedVersion)}>
                    {tr(`Bei ${p.installedVersion} halten`, `Hold at ${p.installedVersion}`)}
                  </Menu.Item>
                ))}
              <Menu.Divider />
              <Menu.Item color="red" onClick={onRemove} disabled={p.autoinstalled}>
                {p.autoinstalled ? tr('Von den Server-Einstellungen installiert', 'Installed by the server’s settings') : tr('Deinstallieren', 'Uninstall')}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        )}
      </Group>

      <Text size="sm" mt="md" c="dimmed" lineClamp={3} style={{ flex: 1 }}>
        {p.description}
      </Text>

      <Stack gap={6} mt="sm">
        {pending && (
          <Text size="xs" c="blue">
            {reloading
              ? tr('Wird auf den Servern geladen …', 'Loading on the servers…')
              : tr('Aktiv nach dem Neuladen der Server (bis zu einer Minute)', 'Live once the servers reload (up to a minute)')}
          </Text>
        )}
        {p.withdrawn && (
          <Text size="xs" c="red">
            {tr('Der Herausgeber hat diese Version zurückgezogen', 'The publisher withdrew this version')}: {p.withdrawn}
          </Text>
        )}
        {p.error && p.installed && !pending && (
          <Text size="xs" c="red" lineClamp={3}>
            {tr('Nicht geladen', 'Not loaded')}: {p.error}
          </Text>
        )}
        {!p.compatible && !p.installed && (
          <Text size="xs" c="orange">
            {p.incompatibleReason || tr('Braucht eine andere Hubra-Version', 'Needs another Hubra version')}
          </Text>
        )}
      </Stack>

      <Card.Section withBorder inheritPadding py="sm" mt="md">
        <Group justify="space-between" wrap="nowrap" gap="sm">
          <PluginState p={p} />
          <Group gap={6} wrap="nowrap">
            <Button size="xs" variant="subtle" color="gray" onClick={onDetails}>
              {tr('Details', 'Details')}
            </Button>
            {!p.installed && (
              <Button size="xs" loading={busy} disabled={!p.compatible} onClick={onInstall} leftSection={<IconDownload size={14} />}>
                {tr('Installieren', 'Install')}
              </Button>
            )}
            {p.update && (
              <Button size="xs" color="gold" loading={busy} onClick={onInstall} leftSection={<IconArrowUp size={14} />}>
                {tr(`Auf ${p.repoVersion}`, `To ${p.repoVersion}`)}
              </Button>
            )}
          </Group>
        </Group>
      </Card.Section>
    </Card>
  )
}

function PluginState({ p }: { p: MarketplacePlugin }) {
  if (!p.installed) {
    return (
      <Text size="xs" c="dimmed">
        {p.repository || p.source || tr('Nicht installiert', 'Not installed')}
      </Text>
    )
  }
  if (p.pendingReload) {
    return (
      <Group gap={6} wrap="nowrap">
        <Loader size={12} />
        <Text size="xs" c="blue">
          {tr('Wird geladen', 'Loading')}
        </Text>
      </Group>
    )
  }
  if (p.error) {
    return (
      <Group gap={6} wrap="nowrap">
        <IconAlertTriangle size={14} color="var(--mantine-color-red-6)" />
        <Text size="xs" c="red">
          {tr('Fehler', 'Error')}
        </Text>
      </Group>
    )
  }
  return (
    <Group gap={6} wrap="nowrap">
      <IconCircleCheck size={14} color="var(--mantine-color-green-6)" />
      <Text size="xs" c="dimmed">
        {p.held ? tr(`Gehalten bei ${p.held}`, `Held at ${p.held}`) : p.update ? tr('Update verfügbar', 'Update available') : tr('Installiert', 'Installed')}
      </Text>
    </Group>
  )
}

function DetailsModal({
  p,
  onClose,
  onInstall,
}: {
  p: MarketplacePlugin
  onClose: () => void
  onInstall: (version: string) => void
}) {
  return (
    <Modal opened onClose={onClose} title={p.name} size="lg" centered>
      <Stack gap="sm">
        <Text size="sm">{p.description}</Text>
        <Group gap={6}>
          <TrustBadge status={p.trust?.status} />
          {p.tags.map((t) => (
            <Badge key={t} size="xs" variant="outline" color="gray">
              {t}
            </Badge>
          ))}
        </Group>
        <Table fz="sm" withRowBorders={false} verticalSpacing={2}>
          <Table.Tbody>
            <Row label={tr('ID', 'Id')} value={<Code>{p.id}</Code>} />
            <Row label={tr('Autor', 'Author')} value={p.author} />
            {p.trust?.signer && (
              <Row label={tr('Signiert von', 'Signed by')} value={`${p.trust.signer} (${p.trust.key_id})`} />
            )}
            {p.trust?.detail && <Row label={tr('Signatur', 'Signature')} value={p.trust.detail} />}
            <Row label={tr('Quelle', 'Source')} value={p.repository || p.source} />
            {p.license && <Row label={tr('Lizenz', 'License')} value={p.license} />}
            {p.homepage && (
              <Row
                label={tr('Website', 'Homepage')}
                value={
                  <Anchor href={p.homepage} target="_blank" rel="noopener noreferrer" size="sm">
                    {p.homepage}
                  </Anchor>
                }
              />
            )}
            {p.modules.length > 0 && <Row label={tr('Module', 'Modules')} value={p.modules.join(', ')} />}
            {p.requires.length > 0 && <Row label={tr('Braucht', 'Needs')} value={p.requires.join(', ')} />}
            {p.depends && Object.keys(p.depends).length > 0 && (
              <Row label={tr('Braucht Plugins', 'Needs plugins')} value={dependsText(p.depends)} />
            )}
            <Row label={tr('Erweitert', 'Extends')} value={usesText(p.uses)} />
          </Table.Tbody>
        </Table>
        {p.changes && (
          <>
            <Text fw={600} size="sm">
              {p.installed ? tr('Änderungen seit deiner Version', 'Changes since your version') : tr('Änderungen', 'Changes')}
            </Text>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {p.changes}
            </Text>
          </>
        )}
        {p.versions.length > 0 && (
          <>
            <Text fw={600} size="sm">
              {tr('Versionen', 'Versions')}
            </Text>
            <Table fz="sm" verticalSpacing={4}>
              <Table.Tbody>
                {p.versions.map((v) => (
                  <Table.Tr key={v.version}>
                    <Table.Td>
                      {v.version}
                      {v.version === p.installedVersion && (
                        <Badge ml={6} size="xs" variant="light" color="gray">
                          {tr('Installiert', 'Installed')}
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td c="dimmed">{v.date}</Table.Td>
                    <Table.Td c={v.yanked ? 'red' : 'dimmed'}>
                      {v.yanked
                        ? `${tr('Zurückgezogen', 'Withdrawn')}: ${v.yanked}`
                        : v.compatible
                          ? ''
                          : `${tr('Braucht Hubra', 'Needs Hubra')} ${v.hubra}`}
                    </Table.Td>
                    <Table.Td w={1}>
                      {v.version !== p.installedVersion && !v.yanked && v.compatible && (
                        <Button
                          size="compact-xs"
                          variant="default"
                          onClick={() => onInstall(v.version)}
                        >
                          {tr('Installieren', 'Install')}
                        </Button>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </>
        )}
      </Stack>
    </Modal>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Table.Tr>
      <Table.Td w={120} c="dimmed">
        {label}
      </Table.Td>
      <Table.Td>{value}</Table.Td>
    </Table.Tr>
  )
}

function StagedModal({
  s,
  onClose,
  onInstalled,
}: {
  s: StagedPlugin
  onClose: () => void
  onInstalled: (out: PluginChange) => void
}) {
  const { notify } = useAdmin()
  const [accept, setAccept] = useState(false)
  const [busy, setBusy] = useState(false)

  const cancel = () => {
    discardStaged(s.token).catch(() => {})
    onClose()
  }
  const confirm = async () => {
    setBusy(true)
    try {
      onInstalled(await confirmStaged(s.token, accept, s.repositoryId))
    } catch (err) {
      notify('error', s.name, errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal opened onClose={cancel} title={tr(`${s.name} ${s.version} installieren?`, `Install ${s.name} ${s.version}?`)} centered>
      <Stack gap="sm">
        <Text size="sm">{s.description}</Text>
        <Group gap={6}>
          <TrustBadge status={s.trust.status} />
          {s.installedVersion && (
            <Badge size="xs" variant="light" color="gray">
              {tr('Ersetzt', 'Replaces')} {s.installedVersion}
            </Badge>
          )}
        </Group>
        <Text size="xs" c="dimmed">
          {s.trust.detail || s.source}
        </Text>
        <Text size="sm">
          {tr('Erweitert', 'Extends')}: {usesText(s.uses)}
        </Text>
        {s.depends && Object.keys(s.depends).length > 0 && (
          <Text size="sm">
            {tr(
              `Braucht ${dependsText(s.depends)}; fehlende Plugins aus derselben Quelle werden zuerst installiert.`,
              `Needs ${dependsText(s.depends)}; missing ones from the same source are installed first.`,
            )}
          </Text>
        )}
        {s.migrations && (
          <Text size="sm">
            {tr(
              'Das Plugin legt Tabellen in der Datenbank jedes Vereins an. Beim Deinstallieren bleiben sie erhalten, ausser du wählst etwas anderes.',
              'It adds tables to the database of every club. Uninstalling keeps them unless you choose otherwise.',
            )}
          </Text>
        )}
        {s.trust.status === 'invalid' && (
          <Alert color="red" variant="light">
            {tr(
              'Die Signatur passt nicht zu den Dateien. Jemand hat das Archiv vielleicht verändert, es kann nicht installiert werden.',
              'The signature doesn’t match the files. Someone may have changed this archive; it can’t be installed.',
            )}
          </Alert>
        )}
        {s.needsConfirmation && (
          <Alert color="orange" variant="light">
            <Stack gap="xs">
              <Text size="sm">
                {tr(
                  'Niemand, dem du vertraust, hat dieses Plugin signiert. Es läuft mit vollem Zugriff auf die Daten aller Vereine. Installiere es nur, wenn du weisst, woher es kommt.',
                  'Nobody you trust signed this plugin. It will run with full access to every club’s data. Only install it if you know where it came from.',
                )}
              </Text>
              <Checkbox
                label={tr('Ich vertraue diesem Code', 'I trust this code')}
                checked={accept}
                onChange={(e) => setAccept(e.currentTarget.checked)}
              />
            </Stack>
          </Alert>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={cancel}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            onClick={confirm}
            loading={busy}
            disabled={!s.installable || (s.needsConfirmation && !accept)}
          >
            {tr('Installieren', 'Install')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function UninstallModal({
  p,
  onClose,
  onRemoved,
}: {
  p: MarketplacePlugin
  onClose: () => void
  onRemoved: (out: PluginChange) => void
}) {
  const { notify } = useAdmin()
  const [deleteData, setDeleteData] = useState(false)
  const [busy, setBusy] = useState(false)
  const remove = async () => {
    setBusy(true)
    try {
      onRemoved(await uninstallPlugin(p.id, deleteData))
    } catch (err) {
      notify('error', p.name, errorText(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal opened onClose={onClose} title={tr(`${p.name} deinstallieren?`, `Uninstall ${p.name}?`)} centered>
      <Stack gap="sm">
        <Text size="sm">
          {tr(
            `Alle Vereine verlieren ${p.name}. Die Daten bleiben erhalten, eine neue Installation bringt alles zurück.`,
            `Every club loses ${p.name}. Its data stays, so installing it again brings everything back.`,
          )}
        </Text>
        <Checkbox
          color="red"
          label={tr('Auch die Daten in allen Vereinen löschen (kann nicht rückgängig gemacht werden)', 'Also delete its data in every club (can’t be undone)')}
          checked={deleteData}
          onChange={(e) => setDeleteData(e.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button color="red" onClick={remove} loading={busy}>
            {tr('Deinstallieren', 'Uninstall')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

// ── Repositories ────────────────────────────────────────────────────────────

function PurposeBadge({ purpose }: { purpose: KeyPurpose }) {
  if (purpose === 'both')
    return (
      <Badge size="xs" variant="light" color="orange">
        {tr('Index + Plugins', 'Index + plugins')}
      </Badge>
    )
  return (
    <Badge size="xs" variant="light" color={purpose === 'index' ? 'acc' : 'gray'}>
      {purpose === 'index' ? tr('Index', 'Index') : tr('Plugins', 'Plugins')}
    </Badge>
  )
}

/** Index key and plugin keys of a repository, one line each. */
function RepositoryKeys({
  keyId,
  separateKeys,
  pluginKeys,
}: {
  keyId: string
  separateKeys: boolean
  pluginKeys: KeyRef[]
}) {
  return (
    <Stack gap={2}>
      <Group gap={6}>
        <PurposeBadge purpose={separateKeys ? 'index' : 'both'} />
        <Code fz="xs">{keyId}</Code>
      </Group>
      {separateKeys &&
        pluginKeys.map((k) => (
          <Group gap={6} key={k.keyId}>
            <PurposeBadge purpose="plugins" />
            <Code fz="xs">{k.keyId}</Code>
            <Text size="xs" c="dimmed">
              {k.name}
            </Text>
          </Group>
        ))}
      {!separateKeys && (
        <Text size="xs" c="orange">
          {tr(
            'Ein Schlüssel signiert die Liste und die Plugins (altes Format).',
            'One key signs the index and the plugins (old format).',
          )}
        </Text>
      )}
    </Stack>
  )
}

function RepositoriesView() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data: repos = [] } = useQuery({ queryKey: ['plugin-repos'], queryFn: listRepositories })
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState<RepositoryPreview | null>(null)
  const [keyId, setKeyId] = useState('')
  const [busy, setBusy] = useState(false)

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['plugin-repos'] })
    queryClient.invalidateQueries({ queryKey: ['marketplace'] })
  }
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
    } catch (err) {
      notify('error', tr('Quellen', 'Repositories'), errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const [confirm, confirmDialog] = useConfirm()
  return (
    <Stack gap="md">
      {confirmDialog}
      <Paper withBorder p="lg">
        <Text fw={600} size="sm" mb={4}>
          {tr('Quelle hinzufügen', 'Add a repository')}
        </Text>
        <Text size="xs" c="dimmed" mb="sm">
          {tr(
            'Die Adresse einer signierten index.json. Ihr Index-Schlüssel und ihre Plugin-Schlüssel werden beim Hinzufügen festgehalten, geänderte Schlüssel werden später abgelehnt.',
            'The address of a signed index.json. Its index key and plugin keys are pinned when you add it, so changed keys are refused later.',
          )}
        </Text>
        <Group align="flex-end" gap="sm">
          <TextInput
            style={{ flex: 1 }}
            placeholder="https://example.org/hubra-plugins/index.json"
            value={url}
            onChange={(e) => {
              setUrl(e.currentTarget.value)
              setPreview(null)
            }}
          />
          <Button
            variant="default"
            loading={busy && !preview}
            onClick={() => act(async () => setPreview(await previewRepository(url.trim())))}
          >
            {tr('Prüfen', 'Look up')}
          </Button>
        </Group>
        {preview && (
          <Stack gap="xs" mt="md">
            <Text size="sm">
              <b>{preview.name}</b>: {preview.plugins} {tr('Plugin(s)', 'plugin(s)')}
            </Text>
            <RepositoryKeys
              keyId={preview.keyId}
              separateKeys={preview.separateKeys}
              pluginKeys={preview.pluginKeys}
            />
            <TextInput
              label={tr(
                'Gib die ID des Index-Schlüssels ein, die du vom Herausgeber erhalten hast',
                'Type the index key id the publisher gave you',
              )}
              description={tr('So weisst du, dass die Liste wirklich von ihm stammt.', 'This is how you know the index really comes from them.')}
              value={keyId}
              onChange={(e) => setKeyId(e.currentTarget.value)}
            />
            <Group justify="flex-end">
              <Button
                disabled={keyId.trim() !== preview.keyId}
                loading={busy}
                onClick={() =>
                  act(async () => {
                    await addRepository(preview.url, keyId.trim())
                    setUrl('')
                    setKeyId('')
                    setPreview(null)
                    refresh()
                  })
                }
              >
                {tr('Quelle hinzufügen', 'Add repository')}
              </Button>
            </Group>
          </Stack>
        )}
      </Paper>
      <Paper withBorder style={{ overflow: 'hidden' }}>
        <Table verticalSpacing="sm" horizontalSpacing="md">
          <Table.Tbody>
            {repos.length === 0 && (
              <Table.Tr>
                <Table.Td c="dimmed" fz="sm">
                  {tr('Noch keine Quellen.', 'No repositories yet.')}
                </Table.Td>
              </Table.Tr>
            )}
            {repos.map((r) => (
              <Table.Tr key={r.id}>
                <Table.Td>
                  <Group gap={6}>
                    <Text size="sm" fw={600}>
                      {r.name}
                    </Text>
                    {r.official && (
                      <Badge size="xs" variant="light" color="green">
                        {tr('Offiziell', 'Official')}
                      </Badge>
                    )}
                  </Group>
                  <Text size="xs" c="dimmed" mb={4}>
                    {r.url}
                  </Text>
                  <RepositoryKeys keyId={r.keyId} separateKeys={r.separateKeys} pluginKeys={r.pluginKeys} />
                  {r.error && (
                    <Text size="xs" c="red">
                      {r.error}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td w={1}>
                  <Group gap="sm" wrap="nowrap">
                    <Switch
                      size="sm"
                      checked={r.enabled}
                      aria-label={tr(`${r.name} verwenden`, `Use ${r.name}`)}
                      onChange={(e) => {
                        const on = e.currentTarget.checked
                        act(async () => {
                          await setRepositoryEnabled(r.id, on)
                          refresh()
                        })
                      }}
                    />
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={() =>
                        confirm({
                          title: tr(`Quelle «${r.name}» entfernen?`, `Remove the repository "${r.name}"?`),
                          body: tr('Installierte Plugins bleiben, bekommen aber keine Updates mehr aus dieser Quelle.', 'Installed plugins stay but get no more updates from it.'),
                          confirmLabel: tr('Entfernen', 'Remove'),
                          run: () =>
                            act(async () => {
                              await deleteRepository(r.id)
                              refresh()
                            }),
                        })
                      }
                    >
                      {tr('Entfernen', 'Remove')}
                    </Button>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>
    </Stack>
  )
}

// ── Signing keys ────────────────────────────────────────────────────────────

function KeysView() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data: keys = [] } = useQuery({ queryKey: ['plugin-keys'], queryFn: listTrustedKeys })
  const [name, setName] = useState('')
  const [pem, setPem] = useState('')
  const [busy, setBusy] = useState(false)

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
      await queryClient.invalidateQueries({ queryKey: ['plugin-keys'] })
    } catch (err) {
      notify('error', tr('Signaturschlüssel', 'Signing keys'), errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const [confirm, confirmDialog] = useConfirm()
  return (
    <Stack gap="md">
      {confirmDialog}
      <Paper withBorder p="lg">
        <Text fw={600} size="sm" mb={4}>
          {tr('Einem Autor vertrauen', 'Trust an author')}
        </Text>
        <Text size="xs" c="dimmed" mb="sm">
          {tr(
            'Jeder Schlüssel hat einen Zweck: Plugins oder Index. Hier fügst du Plugin-Schlüssel hinzu; Plugins mit ihrer Signatur werden als Community installiert. Index-Schlüssel kommen mit ihrer Quelle. Autoren erstellen einen Schlüssel mit',
            'Every key has one purpose: plugins or index. Here you add plugin keys; plugins signed with one install as Community. Index keys come with their repository. Authors create a key with',
          )}{' '}
          <Code>flask plugins keygen</Code>{' '}
          {tr('und schicken dir die .pub-Datei.', 'and send you the .pub file.')}
        </Text>
        <Stack gap="sm">
          <TextInput label={tr('Name', 'Name')} value={name} onChange={(e) => setName(e.currentTarget.value)} />
          <Group gap={6}>
            <Text size="sm">{tr('Zweck', 'Purpose')}:</Text>
            <PurposeBadge purpose="plugins" />
          </Group>
          <Textarea
            label={tr('Öffentlicher Schlüssel', 'Public key')}
            placeholder="-----BEGIN PUBLIC KEY-----"
            autosize
            minRows={3}
            styles={{ input: { fontFamily: 'monospace', fontSize: 12 } }}
            value={pem}
            onChange={(e) => setPem(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button
              loading={busy}
              disabled={!name.trim() || !pem.trim()}
              onClick={() =>
                act(async () => {
                  await addTrustedKey(name.trim(), pem.trim())
                  setName('')
                  setPem('')
                })
              }
            >
              {tr('Schlüssel vertrauen', 'Trust key')}
            </Button>
          </Group>
        </Stack>
      </Paper>
      <Paper withBorder style={{ overflow: 'hidden' }}>
        <Table verticalSpacing="sm" horizontalSpacing="md">
          <Table.Tbody>
            {keys.map((k) => (
              <Table.Tr key={k.keyId}>
                <Table.Td>
                  <Group gap={6}>
                    <Text size="sm" fw={600}>
                      {k.name}
                    </Text>
                    <PurposeBadge purpose={k.purpose} />
                    {k.official && (
                      <Badge size="xs" variant="light" color="green">
                        {tr('Offiziell', 'Official')}
                      </Badge>
                    )}
                  </Group>
                  <Text size="xs" c="dimmed">
                    {k.keyId}
                    {k.source === 'repository' && k.repository
                      ? ` · ${tr('von der Quelle', 'from repository')} ${k.repository}`
                      : ''}
                    {k.addedBy ? ` · ${tr('hinzugefügt von', 'added by')} ${k.addedBy}` : ''}
                  </Text>
                </Table.Td>
                <Table.Td w={1}>
                  {k.id !== null && (
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={() =>
                        confirm({
                          title: tr(`Schlüssel «${k.name}» entfernen?`, `Remove the key "${k.name}"?`),
                          body: tr('Plugins und Listen, die nur mit diesem Schlüssel signiert sind, gelten dann nicht mehr als vertrauenswürdig.', 'Plugins and indexes signed only with this key are no longer trusted.'),
                          confirmLabel: tr('Entfernen', 'Remove'),
                          run: () => act(() => deleteTrustedKey(k.id!)),
                        })
                      }
                    >
                      {tr('Entfernen', 'Remove')}
                    </Button>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>
    </Stack>
  )
}
