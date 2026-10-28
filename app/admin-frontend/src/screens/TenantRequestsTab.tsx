import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Table,
  Paper,
  Badge,
  Button,
  Group,
  Text,
  Modal,
  TextInput,
  Select,
  Stack,
  Alert,
} from '@mantine/core'
import { IconPlus } from '@tabler/icons-react'
import {
  listTenantRequests,
  listMyTenantRequests,
  createTenantRequest,
  approveTenantRequest,
  rejectTenantRequest,
  type TenantRequest,
} from '@/api/tenants'
import { useAdmin } from '@/context/AdminContext'

const STATUS_COLORS: Record<string, string> = {
  pending: 'yellow',
  approved: 'green',
  rejected: 'red',
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-{2,}/g, '-')
}

export function TenantRequestsTab() {
  const { isSuperadmin, notify } = useAdmin()
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [rejectTarget, setRejectTarget] = useState<TenantRequest | null>(null)
  const [rejectNote, setRejectNote] = useState('')
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [plan, setPlan] = useState('starter')
  const [formError, setFormError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['tenant-requests', isSuperadmin],
    queryFn: () =>
      isSuperadmin
        ? listTenantRequests()
        : listMyTenantRequests(),
  })

  const createMutation = useMutation({
    mutationFn: createTenantRequest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-requests'] })
      notify('success', 'Request submitted', 'Your tenant request has been submitted for review.')
      setCreateOpen(false)
      setName('')
      setSlug('')
      setSlugEdited(false)
      setFormError('')
    },
    onError: (err: Error) => {
      setFormError(err.message)
    },
  })

  const approveMutation = useMutation({
    mutationFn: (id: number) => approveTenantRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-requests'] })
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      notify('success', 'Request approved', 'Tenant has been provisioned.')
    },
    onError: (err: Error) => {
      notify('error', 'Approval failed', err.message)
    },
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) =>
      rejectTenantRequest(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-requests'] })
      notify('success', 'Request rejected', 'The tenant request has been rejected.')
      setRejectTarget(null)
      setRejectNote('')
    },
    onError: (err: Error) => {
      notify('error', 'Reject failed', err.message)
    },
  })

  const handleNameChange = (val: string) => {
    setName(val)
    if (!slugEdited) setSlug(slugify(val))
  }

  const handleCreate = () => {
    if (!name || !slug) {
      setFormError('Name and slug are required')
      return
    }
    createMutation.mutate({ name, slug, plan })
  }

  const requests = data?.requests ?? []

  return (
    <div>
      <Group justify="space-between" mb={16}>
        <Text fw={600} size="lg">
          {isSuperadmin ? 'All Tenant Requests' : 'My Tenant Requests'}
        </Text>
        {!isSuperadmin && (
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => setCreateOpen(true)}
          >
            Request New Tenant
          </Button>
        )}
      </Group>

      <Paper withBorder shadow="sm" radius="lg">
        {isLoading && (
          <Text p={40} ta="center" c="dimmed">
            Loading requests...
          </Text>
        )}

        {!isLoading && requests.length === 0 && (
          <Text p={40} ta="center" c="dimmed">
            No tenant requests.
          </Text>
        )}

        {requests.length > 0 && (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Slug</Table.Th>
                <Table.Th>Plan</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Created</Table.Th>
                {isSuperadmin && <Table.Th>Actions</Table.Th>}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {requests.map((r: TenantRequest) => (
                <Table.Tr key={r.id}>
                  <Table.Td fw={600}>{r.name}</Table.Td>
                  <Table.Td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14 }}>
                    {r.slug}
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color="blue" size="sm">
                      {r.plan}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS_COLORS[r.status] ?? 'gray'} size="sm">
                      {r.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td style={{ color: '#6b7480', fontSize: 14 }}>
                    {r.created_at ? new Date(r.created_at).toLocaleDateString() : '-'}
                  </Table.Td>
                  {isSuperadmin && (
                    <Table.Td>
                      {r.status === 'pending' && (
                        <Group gap="xs">
                          <Button
                            size="xs"
                            color="green"
                            variant="light"
                            loading={approveMutation.isPending}
                            onClick={() => approveMutation.mutate(r.id)}
                          >
                            Approve
                          </Button>
                          <Button
                            size="xs"
                            color="red"
                            variant="light"
                            onClick={() => setRejectTarget(r)}
                          >
                            Reject
                          </Button>
                        </Group>
                      )}
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Request New Tenant" size="md">
        <Stack gap={16}>
          {formError && (
            <Alert color="red" variant="light">
              {formError}
            </Alert>
          )}
          <TextInput
            label="Tenant Name"
            required
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="Acme Canoe Club"
          />
          <TextInput
            label="Slug"
            required
            value={slug}
            onChange={(e) => {
              setSlug(e.target.value)
              setSlugEdited(true)
            }}
            placeholder="acme-canoe-club"
            description="URL-safe identifier (3-64 chars, lowercase, hyphens)"
          />
          <Select
            label="Plan"
            value={plan}
            onChange={(v) => v && setPlan(v)}
            data={[
              { value: 'starter', label: 'Starter' },
              { value: 'growth', label: 'Growth' },
              { value: 'enterprise', label: 'Enterprise' },
            ]}
          />
          <Group justify="flex-end" mt={8}>
            <Button variant="default" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button loading={createMutation.isPending} onClick={handleCreate}>
              Submit Request
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={!!rejectTarget}
        onClose={() => { setRejectTarget(null); setRejectNote('') }}
        title="Reject Tenant Request"
        size="md"
      >
        <Stack gap={16}>
          <Text size="sm" c="dimmed">
            Rejecting <strong>{rejectTarget?.name}</strong> ({rejectTarget?.slug}).
            The requester will be able to submit a new request with a different slug.
          </Text>
          <TextInput
            label="Note (optional)"
            value={rejectNote}
            onChange={(e) => setRejectNote(e.target.value)}
            placeholder="Reason for rejection"
          />
          <Group justify="flex-end" mt={8}>
            <Button variant="default" onClick={() => { setRejectTarget(null); setRejectNote('') }}>
              Cancel
            </Button>
            <Button
              color="red"
              loading={rejectMutation.isPending}
              onClick={() => rejectTarget && rejectMutation.mutate({ id: rejectTarget.id, note: rejectNote || undefined })}
            >
              Reject Request
            </Button>
          </Group>
        </Stack>
      </Modal>
    </div>
  )
}
