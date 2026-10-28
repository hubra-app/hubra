import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Table,
  TextInput,
  Button,
  Badge,
  Group,
  Stack,
  Paper,
  Text,
  Modal,
  Alert,
  CopyButton,
  ActionIcon,
} from '@mantine/core'
import { IconPlus, IconTrash, IconCheck, IconCopy, IconStar } from '@tabler/icons-react'
import {
  listDomains,
  addDomain,
  verifyDomain,
  removeDomain,
  setPrimaryDomain,
  type Domain,
} from '@/api/admin'
import { useToast } from '@/context/AppContext'

const STATUS_COLORS: Record<string, string> = {
  verified: 'green',
  pending: 'orange',
  failed: 'red',
}

export function DomainsTab() {
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [newDomain, setNewDomain] = useState('')
  const [adding, setAdding] = useState(false)
  const [txtInstructions, setTxtInstructions] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Domain | null>(null)

  const { data: domains = [], isLoading } = useQuery({
    queryKey: ['domains'],
    queryFn: listDomains,
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['domains'] })

  const handleAdd = async () => {
    if (!newDomain.trim()) return
    setAdding(true)
    try {
      const result = await addDomain(newDomain.trim().toLowerCase())
      setTxtInstructions(result.txt_record.instructions)
      refresh()
      notify('success', 'Domain added', 'Add the TXT record to verify ownership.')
    } catch (err) {
      notify('error', 'Failed to add domain', err instanceof Error ? err.message : undefined)
    } finally {
      setAdding(false)
    }
  }

  const handleVerify = async (domain: Domain) => {
    try {
      const result = await verifyDomain(domain.id)
      if (result.verified) {
        notify('success', 'Domain verified', domain.domain)
      } else {
        notify('error', 'Verification failed', result.error ?? undefined)
      }
      refresh()
    } catch (err) {
      notify('error', 'Verification failed', err instanceof Error ? err.message : undefined)
    }
  }

  const handleRemove = async (id: number) => {
    try {
      await removeDomain(id)
      notify('success', 'Domain removed')
      refresh()
    } catch {
      notify('error', 'Failed to remove domain')
    }
    setDeleteTarget(null)
  }

  const handleSetPrimary = async (domain: Domain) => {
    try {
      await setPrimaryDomain(domain.id)
      notify('success', 'Primary domain set', domain.domain)
      refresh()
    } catch (err) {
      notify('error', 'Failed to set primary', err instanceof Error ? err.message : undefined)
    }
  }

  return (
    <Stack gap={20}>
      <Group justify="space-between">
        <Text fw={700} fz="lg">Custom Domains</Text>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setAddOpen(true)}>
          Add Domain
        </Button>
      </Group>

      <Paper withBorder shadow="sm" radius="lg">
        {isLoading && <Text p={20} c="dimmed">Loading domains...</Text>}
        {!isLoading && domains.length === 0 && (
          <Text p={40} ta="center" c="dimmed">No domains configured.</Text>
        )}
        {domains.length > 0 && (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Domain</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Primary</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {domains.map((d) => (
                <Table.Tr key={d.id}>
                  <Table.Td fw={600}>{d.domain}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS_COLORS[d.verification_status] ?? 'gray'} size="sm">
                      {d.verification_status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {d.is_primary ? (
                      <IconStar size={16} fill="#fece2b" color="#fece2b" />
                    ) : (
                      d.verified && (
                        <IconStar
                          size={16}
                          color="#99a2ac"
                          style={{ cursor: 'pointer' }}
                          onClick={() => handleSetPrimary(d)}
                        />
                      )
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={6}>
                      {d.verification_status !== 'verified' && (
                        <Button size="xs" variant="light" onClick={() => handleVerify(d)}>
                          Verify
                        </Button>
                      )}
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => setDeleteTarget(d)}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={addOpen} onClose={() => { setAddOpen(false); setTxtInstructions(null); setNewDomain('') }} title="Add Domain">
        <Stack gap={14}>
          {txtInstructions ? (
            <Alert icon={<IconCheck size={16} />} color="blue" variant="light">
              <Stack gap={8}>
                <Text fw={600}>Add this TXT record to your DNS:</Text>
                <Group gap={6}>
                  <Text className="num" fz="sm" style={{ wordBreak: 'break-all' }}>
                    {txtInstructions}
                  </Text>
                  <CopyButton value={txtInstructions} timeout={2000}>
                    {({ copied, copy }) => (
                      <ActionIcon color={copied ? 'teal' : 'gray'} onClick={copy}>
                        {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                      </ActionIcon>
                    )}
                  </CopyButton>
                </Group>
                <Text size="sm" c="dimmed">
                  Once added, click "Verify" to check ownership.
                </Text>
              </Stack>
            </Alert>
          ) : (
            <>
              <TextInput
                label="Domain"
                placeholder="example.com"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
              />
              <Group justify="flex-end">
                <Button variant="default" onClick={() => setAddOpen(false)}>Cancel</Button>
                <Button loading={adding} onClick={handleAdd}>Add</Button>
              </Group>
            </>
          )}
        </Stack>
      </Modal>

      <Modal
        opened={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Remove Domain"
        size="sm"
      >
        <Stack gap={14}>
          <Text>Are you sure you want to remove <strong>{deleteTarget?.domain}</strong>?</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button color="red" onClick={() => deleteTarget && handleRemove(deleteTarget.id)}>
              Remove
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
