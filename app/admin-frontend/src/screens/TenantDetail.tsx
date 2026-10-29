import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'
import { planLabel, statusLabel } from '@/labels'
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
import { ClubAdminsPanel } from '@/screens/ClubAdmins'

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  suspended: 'orange',
  archived: 'gray',
}

const ACTION_DONE: Record<'disable' | 'enable' | 'archive', () => string> = {
  disable: () => tr('Verein gesperrt', 'Club suspended'),
  enable: () => tr('Verein aktiviert', 'Club enabled'),
  archive: () => tr('Verein archiviert', 'Club archived'),
}

export function TenantDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { notify } = useAdmin()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [pendingAction, setPendingAction] = useState<string | null>(null)
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
      notify('success', tr('Person hinzugefügt', 'Member added'), memberEmail)
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

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] })
    // The club list and the backup club list show the status too.
    queryClient.invalidateQueries({ queryKey: ['tenants'] })
    queryClient.invalidateQueries({ queryKey: ['backup-clubs'] })
  }

  const handleAction = async (
    action: 'disable' | 'enable' | 'archive',
    fn: (id: number) => Promise<unknown>,
  ) => {
    if (pendingAction) return
    setPendingAction(action)
    try {
      await fn(tenantId)
      notify('success', ACTION_DONE[action](), tenant?.name)
      refresh()
    } catch (err) {
      notify('error', tr('Aktion fehlgeschlagen', 'Action failed'), err instanceof Error ? err.message : undefined)
    } finally {
      setPendingAction(null)
    }
  }

  const handleDelete = async (force: boolean) => {
    try {
      await deleteTenant(tenantId, force)
      notify('success', tr('Verein gelöscht', 'Club deleted'), tenant?.name)
      refresh()
      navigate('/app/tenants')
    } catch (err) {
      notify('error', tr('Löschen fehlgeschlagen', 'Delete failed'), err instanceof Error ? err.message : undefined)
    }
  }

  if (isLoading) {
    return (
      <Text p={40} ta="center" c="dimmed">
        {tr('Verein wird geladen …', 'Loading club…')}
      </Text>
    )
  }

  if (error || !tenant) {
    return (
      <Stack p={40} align="center">
        <Text c="red">{tr('Verein konnte nicht geladen werden', 'Could not load the club')}</Text>
        <Button variant="default" onClick={() => navigate('/app/tenants')}>
          {tr('Zurück zu allen Vereinen', 'Back to all clubs')}
        </Button>
      </Stack>
    )
  }

  return (
    <div>
      <Button
        variant="subtle"
        color="gray"
        size="xs"
        ml={-8}
        mb="sm"
        leftSection={<IconArrowLeft size={14} />}
        onClick={() => navigate('/app/tenants')}
      >
        {tr('Alle Vereine', 'All clubs')}
      </Button>
      <Group justify="space-between" align="flex-end" gap="md" mb={28} wrap="wrap">
        <Stack gap={8}>
          <Title order={1}>{tenant.name}</Title>
          <Group gap={8}>
            <Text fz="sm" className="num" c="dimmed">
              {tenant.slug}
            </Text>
            <Badge variant="light" color={STATUS_COLORS[tenant.status] ?? 'gray'}>
              {statusLabel(tenant.status, tr)}
            </Badge>
            <Badge variant="light" color="acc">
              {planLabel(tenant.plan, tr)}
            </Badge>
          </Group>
        </Stack>
        <Group gap={8} wrap="wrap">
          {tenant.status === 'active' ? (
            <Button
              variant="default"
              leftSection={<IconBan size={16} />}
              onClick={() => handleAction('disable', disableTenant)}
              loading={pendingAction === 'disable'}
            >
              {tr('Sperren', 'Suspend')}
            </Button>
          ) : (
            <Button
              variant="default"
              leftSection={<IconCheck size={16} />}
              onClick={() => handleAction('enable', enableTenant)}
              loading={pendingAction === 'enable'}
            >
              {tr('Aktivieren', 'Enable')}
            </Button>
          )}
          <Button
            variant="default"
            leftSection={<IconArchive size={16} />}
            onClick={() => handleAction('archive', archiveTenant)}
            loading={pendingAction === 'archive'}
          >
            {tr('Archivieren', 'Archive')}
          </Button>
          <Button
            color="red"
            variant="light"
            leftSection={<IconTrash size={16} />}
            onClick={() => setDeleteOpen(true)}
          >
            {tr('Löschen', 'Delete')}
          </Button>
          <Button
            variant="filled"
            leftSection={<IconReplaceUser size={16} />}
            onClick={() => setImpersonateOpen(true)}
          >
            {tr('Als Admin öffnen', 'Impersonate')}
          </Button>
        </Group>
      </Group>

      {usage && (
        <StatGrid columns={4}>
          <StatTile label={tr('Mitglieder', 'Members')} value={usage.member_count} />
          <StatTile label={tr('Domains', 'Domains')} value={usage.domain_count} />
          <StatTile label={tr('Benutzerkonten', 'Users')} value={usage.user_count} />
          <StatTile label={tr('Audit-Einträge', 'Audit entries')} value={usage.audit_entry_count} />
        </StatGrid>
      )}

      <Paper withBorder p="lg" mb={20}>
        <Title order={3} mb={12}>
          {tr('Details', 'Details')}
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
              {tr('Erstellt', 'Created')}
            </Text>
            <Text fw={600}>{tenant.created_at ? formatDateTime(tenant.created_at) : '–'}</Text>
          </Group>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              {tr('Geändert', 'Updated')}
            </Text>
            <Text fw={600}>{tenant.updated_at ? formatDateTime(tenant.updated_at) : '–'}</Text>
          </Group>
          {tenant.deleted_at && (
            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                {tr('Gelöscht', 'Deleted')}
              </Text>
              <Text fw={600} c="red">
                {formatDateTime(tenant.deleted_at)}
              </Text>
            </Group>
          )}
        </Stack>
      </Paper>

      <ClubAdminsPanel tenantId={tenant.id} />

      <TenantModules tenantId={tenant.id} />

      <Paper withBorder p="lg" mb={20}>
        <Group justify="space-between" mb={12}>
          <Title order={3}>{tr('Mitglieder', 'Members')}</Title>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconUserPlus size={16} />}
            onClick={() => setAddMemberOpen(true)}
          >
            {tr('Person hinzufügen', 'Add person')}
          </Button>
        </Group>
        {members.length === 0 ? (
          <Text p={20} ta="center" c="dimmed">
            {tr('Noch keine Mitglieder.', 'No members yet.')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={560}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Name', 'Name')}</Table.Th>
                <Table.Th>{tr('E-Mail', 'Email')}</Table.Th>
                <Table.Th>{tr('Rollen', 'Roles')}</Table.Th>
                <Table.Th>{tr('Status', 'Status')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {members.map((m) => (
                <Table.Tr key={m.id}>
                  <Table.Td fw={600}>{m.name}</Table.Td>
                  <Table.Td>{m.email}</Table.Td>
                  <Table.Td>
                    {m.roles.map((r) => (
                      <Badge key={r} variant="light" color="acc" size="sm" mr={4}>
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
                      {statusLabel(m.status, tr)}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          </Table.ScrollContainer>
        )}
      </Paper>

      <Modal
        opened={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={tr('Verein löschen', 'Delete club')}
        size="md"
      >
        <Stack gap={16}>
          <Alert color="red" variant="light" icon={<IconTrash size={16} />}>
            {tr(
              `«${tenant.name}» wird archiviert und aus den Listen ausgeblendet. Die Daten bleiben erhalten.`,
              `"${tenant.name}" will be archived and hidden from the lists. Its data is kept.`,
            )}
          </Alert>
          <Text size="sm" c="dimmed">
            {tr(
              'Endgültig löschen entfernt den Verein mit allen Daten. Das kann nicht rückgängig gemacht werden.',
              'Delete permanently removes the club with all its data. This cannot be undone.',
            )}
          </Text>
          <Group justify="flex-end" gap={8}>
            <Button variant="default" onClick={() => setDeleteOpen(false)}>
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button
              variant="light"
              onClick={() => {
                setDeleteOpen(false)
                handleDelete(false)
              }}
            >
              {tr('Archivieren', 'Archive')}
            </Button>
            <Button
              color="red"
              onClick={() => {
                setDeleteOpen(false)
                handleDelete(true)
              }}
            >
              {tr('Endgültig löschen', 'Delete permanently')}
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
        title={tr('Person zum Verein hinzufügen', 'Add a person to the club')}
        size="md"
      >
        <Stack gap={16}>
          {memberError && (
            <Alert color="red" variant="light">
              {memberError}
            </Alert>
          )}
          <TextInput
            label={tr('E-Mail-Adresse', 'Email address')}
            required
            value={memberEmail}
            onChange={(e) => setMemberEmail(e.target.value)}
            placeholder="name@example.ch"
            description={tr('Die Person braucht bereits ein Hubra-Konto. Sie wird als Mitglied mit der Standardrolle hinzugefügt.', 'The person needs a Hubra account already. They are added as a member with the default role.')}
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
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button
              loading={addMemberMutation.isPending}
              onClick={() => {
                if (!memberEmail.trim()) {
                  setMemberError(tr('E-Mail-Adresse ist erforderlich', 'Email is required'))
                  return
                }
                addMemberMutation.mutate()
              }}
            >
              {tr('Hinzufügen', 'Add')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </div>
  )
}
