import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDateTime } from '@/format'
import {
  Paper,
  Badge,
  Button,
  Group,
  Stack,
  Text,
  Title,
  Alert,
  Modal,
  Table,
  TextInput,
} from '@mantine/core'
import {
  IconArrowLeft,
  IconBan,
  IconCheck,
  IconArchive,
  IconTrash,
  IconReplaceUser,
  IconUserPlus,
} from '@tabler/icons-react'
import { useState } from 'react'
import {
  getTenant,
  disableTenant,
  enableTenant,
  archiveTenant,
  deleteTenant,
  listTenantMembers,
  addTenantMember,
} from '@/api/tenants'
import { useAdmin } from '@/context/AdminContext'
import { StatTile, StatGrid } from '@/components/ui'
import { ImpersonateModal } from '@/screens/ImpersonateModal'
import { TenantModules } from '@/screens/TenantModules'

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  suspended: 'orange',
  archived: 'gray',
}

export function TenantDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { notify } = useAdmin()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [impersonateOpen, setImpersonateOpen] = useState(false)
  const [addMemberOpen, setAddMemberOpen] = useState(false)
  const [memberEmail, setMemberEmail] = useState('')
  const [memberError, setMemberError] = useState('')
  const tenantId = Number(id)

  const { data, isLoading, error } = useQuery({
    queryKey: ['tenant', tenantId],
    queryFn: () => getTenant(tenantId),
    enabled: !!tenantId,
  })

  const { data: membersData } = useQuery({
    queryKey: ['tenant-members', tenantId],
    queryFn: () => listTenantMembers(tenantId),
    enabled: !!tenantId,
  })

  const addMemberMutation = useMutation({
    mutationFn: () => addTenantMember(tenantId, { email: memberEmail.trim().toLowerCase() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-members', tenantId] })
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] })
      notify('success', 'Member added', memberEmail)
      setAddMemberOpen(false)
      setMemberEmail('')
      setMemberError('')
    },
    onError: (err: Error) => {
      setMemberError(err.message)
    },
  })

  const tenant = data?.tenant
  const usage = tenant?.usage
  const members = membersData?.members ?? []

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] })

  const handleAction = async (
    action: 'disable' | 'enable' | 'archive',
    fn: (id: number) => Promise<unknown>,
  ) => {
    try {
      await fn(tenantId)
      notify('success', `Tenant ${action}d`, tenant?.name)
      refresh()
    } catch (err) {
      notify('error', 'Action failed', err instanceof Error ? err.message : undefined)
    }
  }

  const handleDelete = async (force: boolean) => {
    try {
      await deleteTenant(tenantId, force)
      notify('success', 'Tenant deleted', tenant?.name)
      navigate('/app/tenants')
    } catch (err) {
      notify('error', 'Delete failed', err instanceof Error ? err.message : undefined)
    }
  }

  if (isLoading) {
    return (
      <Text p={40} ta="center" c="dimmed">
        Loading tenant...
      </Text>
    )
  }

  if (error || !tenant) {
    return (
      <Stack p={40} align="center">
        <Text c="red">Failed to load tenant</Text>
        <Button variant="default" onClick={() => navigate('/app/tenants')}>
          Back to Tenants
        </Button>
      </Stack>
    )
  }

  return (
    <div>
      <Group justify="space-between" mb={20}>
        <Group gap={12}>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate('/app/tenants')}
          >
            Back
          </Button>
          <div className="eyebrow">Tenant</div>
        </Group>
        <Group gap={8}>
          {tenant.status === 'active' ? (
            <Button
              variant="default"
              leftSection={<IconBan size={16} />}
              onClick={() => handleAction('disable', disableTenant)}
            >
              Disable
            </Button>
          ) : (
            <Button
              variant="default"
              leftSection={<IconCheck size={16} />}
              onClick={() => handleAction('enable', enableTenant)}
            >
              Enable
            </Button>
          )}
          <Button
            variant="default"
            leftSection={<IconArchive size={16} />}
            onClick={() => handleAction('archive', archiveTenant)}
          >
            Archive
          </Button>
          <Button
            color="red"
            variant="light"
            leftSection={<IconTrash size={16} />}
            onClick={() => setDeleteOpen(true)}
          >
            Delete
          </Button>
          <Button
            variant="filled"
            leftSection={<IconReplaceUser size={16} />}
            onClick={() => setImpersonateOpen(true)}
          >
            Impersonate
          </Button>
        </Group>
      </Group>

      <Title order={1} mb={4}>
        {tenant.name}
      </Title>
      <Group gap={12} mb={24}>
        <Text fz="sm" style={{ fontFamily: "'JetBrains Mono', monospace" }} c="dimmed">
          {tenant.slug}
        </Text>
        <Badge variant="light" color={STATUS_COLORS[tenant.status] ?? 'gray'}>
          {tenant.status}
        </Badge>
        <Badge variant="light" color="blue">
          {tenant.plan}
        </Badge>
      </Group>

      {usage && (
        <StatGrid columns={4}>
          <StatTile label="Members" value={usage.member_count} />
          <StatTile label="Domains" value={usage.domain_count} />
          <StatTile label="Users" value={usage.user_count} />
          <StatTile label="Audit Entries" value={usage.audit_entry_count} />
        </StatGrid>
      )}

      <Paper withBorder shadow="sm" radius="lg" p="lg" mb={20}>
        <Title order={3} mb={12}>
          Tenant Details
        </Title>
        <Stack gap={8}>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              ID
            </Text>
            <Text className="num" fw={600}>
              {tenant.id}
            </Text>
          </Group>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              Created
            </Text>
            <Text fw={600}>{tenant.created_at ? formatDateTime(tenant.created_at) : '-'}</Text>
          </Group>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              Updated
            </Text>
            <Text fw={600}>{tenant.updated_at ? formatDateTime(tenant.updated_at) : '-'}</Text>
          </Group>
          {tenant.deleted_at && (
            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                Deleted
              </Text>
              <Text fw={600} c="red">
                {formatDateTime(tenant.deleted_at)}
              </Text>
            </Group>
          )}
        </Stack>
      </Paper>

      <TenantModules tenantId={tenant.id} />

      <Paper withBorder shadow="sm" radius="lg" p="lg" mb={20}>
        <Group justify="space-between" mb={12}>
          <Title order={3}>Members</Title>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconUserPlus size={16} />}
            onClick={() => setAddMemberOpen(true)}
          >
            Add User
          </Button>
        </Group>
        {members.length === 0 ? (
          <Text p={20} ta="center" c="dimmed">
            No members found.
          </Text>
        ) : (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Email</Table.Th>
                <Table.Th>Roles</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {members.map((m) => (
                <Table.Tr key={m.id}>
                  <Table.Td fw={600}>{m.name}</Table.Td>
                  <Table.Td>{m.email}</Table.Td>
                  <Table.Td>
                    {m.roles.map((r) => (
                      <Badge key={r} variant="light" color="blue" size="sm" mr={4}>
                        {r}
                      </Badge>
                    ))}
                  </Table.Td>
                  <Table.Td>
                    <Badge
                      variant="light"
                      color={m.status === 'active' ? 'green' : 'gray'}
                      size="sm"
                    >
                      {m.status}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal
        opened={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Delete Tenant"
        size="md"
      >
        <Stack gap={16}>
          <Alert color="red" variant="light" icon={<IconTrash size={16} />}>
            This will soft-delete "{tenant.name}". The tenant will be archived and excluded from
            default lists. Data is preserved.
          </Alert>
          <Text size="sm" c="dimmed">
            To permanently delete (drop schema + remove record), use the force option below. This
            cannot be undone.
          </Text>
          <Group justify="flex-end" gap={8}>
            <Button variant="default" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="light"
              onClick={() => {
                setDeleteOpen(false)
                handleDelete(false)
              }}
            >
              Soft Delete
            </Button>
            <Button
              color="red"
              onClick={() => {
                setDeleteOpen(false)
                handleDelete(true)
              }}
            >
              Force Delete
            </Button>
          </Group>
        </Stack>
      </Modal>

      <ImpersonateModal
        opened={impersonateOpen}
        onClose={() => setImpersonateOpen(false)}
        tenantId={tenantId}
        tenantName={tenant.name}
      />

      <Modal
        opened={addMemberOpen}
        onClose={() => {
          setAddMemberOpen(false)
          setMemberError('')
          setMemberEmail('')
        }}
        title="Add User to Tenant"
        size="md"
      >
        <Stack gap={16}>
          {memberError && (
            <Alert color="red" variant="light">
              {memberError}
            </Alert>
          )}
          <TextInput
            label="User Email"
            required
            value={memberEmail}
            onChange={(e) => setMemberEmail(e.target.value)}
            placeholder="user@example.ch"
            description="The user must already have an account. They will be added as a member with the default role."
          />
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => {
                setAddMemberOpen(false)
                setMemberError('')
                setMemberEmail('')
              }}
            >
              Cancel
            </Button>
            <Button
              loading={addMemberMutation.isPending}
              onClick={() => {
                if (!memberEmail.trim()) {
                  setMemberError('Email is required')
                  return
                }
                addMemberMutation.mutate()
              }}
            >
              Add Member
            </Button>
          </Group>
        </Stack>
      </Modal>
    </div>
  )
}
