import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Checkbox,
  Code,
  FileButton,
  Group,
  Menu,
  Modal,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core'
import { IconDots, IconRefresh, IconUpload } from '@tabler/icons-react'
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
} from '@/api/plugins'

const TRUST: Record<string, { color: string; label: string }> = {
  bundled: { color: 'green', label: 'Shipped with Hubra' },
  official: { color: 'green', label: 'Official' },
  community: { color: 'blue', label: 'Community' },
  unsigned: { color: 'orange', label: 'Unsigned' },
  invalid: { color: 'red', label: 'Invalid signature' },
}

function TrustBadge({ status }: { status: string }) {
  const t = TRUST[status]
  if (!t) return null
  return (
    <Badge size="xs" variant="light" color={t.color}>
      {t.label}
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
          { value: 'plugins', label: 'Plugins' },
          { value: 'repositories', label: 'Repositories' },
          { value: 'keys', label: 'Signing keys' },
        ]}
      />
      {view === 'plugins' && <PluginsView />}
      {view === 'repositories' && <RepositoriesView />}
      {view === 'keys' && <KeysView />}
    </Stack>
  )
}

// ── Plugins ─────────────────────────────────────────────────────────────────

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
        notify('success', 'Plugins reloaded', 'The change is live.')
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
      notify('error', 'Plugins', errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const install = (p: MarketplacePlugin, version?: string) =>
    run(p.id, async () => {
      const out = await installPlugin(p.id, {
        version,
        repositoryId: version || !p.bundled ? p.repositoryId : undefined,
      })
      if (out.installed) changed(out.installed, 'Installed')
      if (out.staged) setStaged(out.staged)
    })

  const upload = (file: File | null) =>
    file &&
    run('upload', async () => {
      setStaged(await uploadPlugin(file))
    })

  const plugins = (data?.plugins ?? []).filter((p) => {
    if (filter === 'installed' && !p.installed) return false
    if (filter === 'updates' && !p.update && !p.withdrawn) return false
    const q = search.trim().toLowerCase()
    return !q || `${p.name} ${p.id} ${p.description} ${p.tags.join(' ')}`.toLowerCase().includes(q)
  })

  return (
    <Stack gap="md">
      {waitFor !== null && (
        <Alert color="blue" variant="light">
          Servers are loading the change. This takes up to a minute.
        </Alert>
      )}
      {data?.errors.map((e) => (
        <Alert key={e} color="orange" variant="light">
          {e}
        </Alert>
      ))}
      <Group justify="space-between" wrap="wrap">
        <Group gap="sm">
          <TextInput
            placeholder="Search"
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
          />
          <SegmentedControl
            value={filter}
            onChange={setFilter}
            data={[
              { value: 'all', label: 'All' },
              { value: 'installed', label: 'Installed' },
              { value: 'updates', label: 'Updates' },
            ]}
          />
        </Group>
        <Group gap="sm">
          <Select
            w={210}
            aria-label="Updates"
            value={data?.updateMode ?? 'notify'}
            onChange={(v) =>
              v &&
              run('mode', async () => {
                await setUpdateMode(v as UpdateMode)
                await queryClient.invalidateQueries({ queryKey: ['marketplace'] })
              })
            }
            data={[
              { value: 'notify', label: 'Updates: tell me' },
              { value: 'official', label: 'Updates: install official' },
              { value: 'off', label: 'Updates: don’t check' },
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
            Check for updates
          </Button>
          <FileButton onChange={upload} accept=".zip,application/zip">
            {(props) => (
              <Button {...props} leftSection={<IconUpload size={16} />} loading={busy === 'upload'}>
                Upload plugin
              </Button>
            )}
          </FileButton>
        </Group>
      </Group>

      <Paper withBorder radius="lg">
        {isLoading ? (
          <Text p="lg" size="sm" c="dimmed">
            Loading…
          </Text>
        ) : error ? (
          <Text p="lg" size="sm" c="red">
            {errorText(error)}
          </Text>
        ) : plugins.length === 0 ? (
          <Text p="lg" size="sm" c="dimmed">
            No plugins match.
          </Text>
        ) : (
          <Table verticalSpacing="sm" horizontalSpacing="md">
            <Table.Tbody>
              {plugins.map((p) => (
                <PluginRow
                  key={p.id}
                  p={p}
                  busy={busy === p.id}
                  onDetails={() => setDetails(p)}
                  onInstall={() => install(p)}
                  onRollback={() =>
                    run(p.id, async () => changed(await rollbackPlugin(p.id), 'Rolled back'))
                  }
                  onHold={(version) =>
                    run(p.id, async () => {
                      await holdPlugin(p.id, version)
                      await queryClient.invalidateQueries({ queryKey: ['marketplace'] })
                    })
                  }
                  onRemove={() => setRemoving(p)}
                />
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

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
            changed(out, 'Installed')
          }}
        />
      )}
      {removing && (
        <UninstallModal
          p={removing}
          onClose={() => setRemoving(null)}
          onRemoved={(out) => {
            setRemoving(null)
            changed(out, 'Removed')
          }}
        />
      )}
    </Stack>
  )
}

function PluginRow({
  p,
  busy,
  onDetails,
  onInstall,
  onRollback,
  onHold,
  onRemove,
}: {
  p: MarketplacePlugin
  busy: boolean
  onDetails: () => void
  onInstall: () => void
  onRollback: () => void
  onHold: (version: string | null) => void
  onRemove: () => void
}) {
  const offered = p.repoVersion ?? p.version
  return (
    <Table.Tr>
      <Table.Td>
        <Group gap={8} mb={2}>
          <Anchor component="button" fw={600} size="sm" c="dark" onClick={onDetails}>
            {p.name}
          </Anchor>
          <Text size="xs" c="dimmed">
            {p.installed ? p.installedVersion : offered}
          </Text>
          <TrustBadge status={p.trust?.status || (p.officialSigned ? 'official' : '')} />
          {p.installed && !p.error && (
            <Badge size="xs" variant="light" color="gray">
              Installed
            </Badge>
          )}
          {p.update && (
            <Badge size="xs" color="yellow">
              Update {p.repoVersion}
            </Badge>
          )}
          {p.held && (
            <Badge size="xs" variant="outline" color="gray">
              Held at {p.held}
            </Badge>
          )}
          {p.withdrawn && (
            <Badge size="xs" color="red">
              Withdrawn
            </Badge>
          )}
        </Group>
        <Text size="xs" c="dimmed">
          {p.description}
          {p.author ? ` · ${p.author}` : ''}
        </Text>
        {p.withdrawn && (
          <Text size="xs" c="red">
            The publisher withdrew this version: {p.withdrawn}
          </Text>
        )}
        {p.error && p.installed && (
          <Text size="xs" c="red">
            Not loaded: {p.error}
          </Text>
        )}
        {!p.compatible && !p.installed && (
          <Text size="xs" c="orange">
            {p.incompatibleReason || 'Needs another Hubra version'}
          </Text>
        )}
      </Table.Td>
      <Table.Td w={1}>
        <Group gap={6} wrap="nowrap" justify="flex-end">
          {!p.installed && (
            <Button size="xs" loading={busy} disabled={!p.compatible} onClick={onInstall}>
              Install
            </Button>
          )}
          {p.update && (
            <Button size="xs" loading={busy} onClick={onInstall}>
              Update
            </Button>
          )}
          {p.installed && (
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <Button size="xs" variant="subtle" px={6} aria-label={`More for ${p.name}`}>
                  <IconDots size={16} />
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item onClick={onDetails}>Details and versions</Menu.Item>
                {p.previous && (
                  <Menu.Item onClick={onRollback}>Roll back to {p.previous}</Menu.Item>
                )}
                {p.repositoryId !== null &&
                  (p.held ? (
                    <Menu.Item onClick={() => onHold(null)}>Allow updates again</Menu.Item>
                  ) : (
                    <Menu.Item onClick={() => onHold(p.installedVersion)}>
                      Hold at {p.installedVersion}
                    </Menu.Item>
                  ))}
                <Menu.Divider />
                <Menu.Item color="red" onClick={onRemove} disabled={p.autoinstalled}>
                  {p.autoinstalled ? 'Installed by the server’s settings' : 'Uninstall'}
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
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
            <Row label="Id" value={<Code>{p.id}</Code>} />
            <Row label="Author" value={p.author} />
            {p.trust?.signer && (
              <Row label="Signed by" value={`${p.trust.signer} (${p.trust.key_id})`} />
            )}
            {p.trust?.detail && <Row label="Signature" value={p.trust.detail} />}
            <Row label="Source" value={p.repository || p.source} />
            {p.license && <Row label="License" value={p.license} />}
            {p.homepage && (
              <Row
                label="Homepage"
                value={
                  <Anchor href={p.homepage} target="_blank" rel="noopener noreferrer" size="sm">
                    {p.homepage}
                  </Anchor>
                }
              />
            )}
            {p.modules.length > 0 && <Row label="Modules" value={p.modules.join(', ')} />}
            {p.requires.length > 0 && <Row label="Needs" value={p.requires.join(', ')} />}
          </Table.Tbody>
        </Table>
        {p.changes && (
          <>
            <Text fw={600} size="sm">
              {p.installed ? 'Changes since your version' : 'Changes'}
            </Text>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {p.changes}
            </Text>
          </>
        )}
        {p.versions.length > 0 && (
          <>
            <Text fw={600} size="sm">
              Versions
            </Text>
            <Table fz="sm" verticalSpacing={4}>
              <Table.Tbody>
                {p.versions.map((v) => (
                  <Table.Tr key={v.version}>
                    <Table.Td>
                      {v.version}
                      {v.version === p.installedVersion && (
                        <Badge ml={6} size="xs" variant="light" color="gray">
                          Installed
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td c="dimmed">{v.date}</Table.Td>
                    <Table.Td c={v.yanked ? 'red' : 'dimmed'}>
                      {v.yanked
                        ? `Withdrawn: ${v.yanked}`
                        : v.compatible
                          ? ''
                          : `Needs Hubra ${v.hubra}`}
                    </Table.Td>
                    <Table.Td w={1}>
                      {v.version !== p.installedVersion && !v.yanked && v.compatible && (
                        <Button
                          size="compact-xs"
                          variant="default"
                          onClick={() => onInstall(v.version)}
                        >
                          Install
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
    <Modal opened onClose={cancel} title={`Install ${s.name} ${s.version}?`} centered>
      <Stack gap="sm">
        <Text size="sm">{s.description}</Text>
        <Group gap={6}>
          <TrustBadge status={s.trust.status} />
          {s.installedVersion && (
            <Badge size="xs" variant="light" color="gray">
              Replaces {s.installedVersion}
            </Badge>
          )}
        </Group>
        <Text size="xs" c="dimmed">
          {s.trust.detail || s.source}
        </Text>
        {s.migrations && (
          <Text size="sm">
            It adds tables to the database of every club. Uninstalling keeps them unless you choose
            otherwise.
          </Text>
        )}
        {s.trust.status === 'invalid' && (
          <Alert color="red" variant="light">
            The signature doesn’t match the files. Someone may have changed this archive; it can’t
            be installed.
          </Alert>
        )}
        {s.needsConfirmation && (
          <Alert color="orange" variant="light">
            <Stack gap="xs">
              <Text size="sm">
                Nobody you trust signed this plugin. It will run with full access to every club’s
                data. Only install it if you know where it came from.
              </Text>
              <Checkbox
                label="I trust this code"
                checked={accept}
                onChange={(e) => setAccept(e.currentTarget.checked)}
              />
            </Stack>
          </Alert>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={cancel}>
            Cancel
          </Button>
          <Button
            onClick={confirm}
            loading={busy}
            disabled={!s.installable || (s.needsConfirmation && !accept)}
          >
            Install
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
    <Modal opened onClose={onClose} title={`Uninstall ${p.name}?`} centered>
      <Stack gap="sm">
        <Text size="sm">
          Every club loses {p.name}. Its data stays, so installing it again brings everything back.
        </Text>
        <Checkbox
          color="red"
          label="Also delete its data in every club (can’t be undone)"
          checked={deleteData}
          onChange={(e) => setDeleteData(e.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button color="red" onClick={remove} loading={busy}>
            Uninstall
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

// ── Repositories ────────────────────────────────────────────────────────────

function RepositoriesView() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data: repos = [] } = useQuery({ queryKey: ['plugin-repos'], queryFn: listRepositories })
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof previewRepository>> | null>(null)
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
      notify('error', 'Repositories', errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Stack gap="md">
      <Paper withBorder radius="lg" p="lg">
        <Text fw={600} size="sm" mb={4}>
          Add a repository
        </Text>
        <Text size="xs" c="dimmed" mb="sm">
          The address of a signed index.json. Its signing key is pinned when you add it, so a
          changed key is refused later.
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
            Look up
          </Button>
        </Group>
        {preview && (
          <Stack gap="xs" mt="md">
            <Text size="sm">
              <b>{preview.name}</b>: {preview.plugins} plugin(s), signed with key{' '}
              <Code>{preview.keyId}</Code>
            </Text>
            <TextInput
              label="Type the key id the publisher gave you"
              description="This is how you know the index really comes from them."
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
                Add repository
              </Button>
            </Group>
          </Stack>
        )}
      </Paper>
      <Paper withBorder radius="lg">
        <Table verticalSpacing="sm" horizontalSpacing="md">
          <Table.Tbody>
            {repos.length === 0 && (
              <Table.Tr>
                <Table.Td c="dimmed" fz="sm">
                  No repositories yet.
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
                        Official
                      </Badge>
                    )}
                  </Group>
                  <Text size="xs" c="dimmed">
                    {r.url} · key {r.keyId}
                  </Text>
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
                      aria-label={`Use ${r.name}`}
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
                        act(async () => {
                          await deleteRepository(r.id)
                          refresh()
                        })
                      }
                    >
                      Remove
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
      notify('error', 'Signing keys', errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Stack gap="md">
      <Paper withBorder radius="lg" p="lg">
        <Text fw={600} size="sm" mb={4}>
          Trust an author
        </Text>
        <Text size="xs" c="dimmed" mb="sm">
          Plugins uploaded with a signature from a key here install as Community. Authors create a
          key with <Code>flask plugins keygen</Code> and send you the .pub file.
        </Text>
        <Stack gap="sm">
          <TextInput label="Name" value={name} onChange={(e) => setName(e.currentTarget.value)} />
          <Textarea
            label="Public key"
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
              Trust key
            </Button>
          </Group>
        </Stack>
      </Paper>
      <Paper withBorder radius="lg">
        <Table verticalSpacing="sm" horizontalSpacing="md">
          <Table.Tbody>
            {keys.map((k) => (
              <Table.Tr key={k.keyId}>
                <Table.Td>
                  <Group gap={6}>
                    <Text size="sm" fw={600}>
                      {k.name}
                    </Text>
                    {k.official && (
                      <Badge size="xs" variant="light" color="green">
                        Official
                      </Badge>
                    )}
                  </Group>
                  <Text size="xs" c="dimmed">
                    {k.keyId}
                    {k.addedBy ? ` · added by ${k.addedBy}` : ''}
                  </Text>
                </Table.Td>
                <Table.Td w={1}>
                  {k.id !== null && (
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={() => act(() => deleteTrustedKey(k.id!))}
                    >
                      Remove
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
