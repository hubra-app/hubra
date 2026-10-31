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
  Stack,
  Alert,
  Checkbox,
  Select,
} from '@mantine/core'
import { IconPlus, IconUserPlus } from '@tabler/icons-react'
import {
  listGlobalRoles,
  listGlobalPermissions,
  createGlobalRole,
  updateGlobalRole,
  searchUsers,
  getUserRoles,
  assignUserRole,
  removeUserRole,
  type GlobalRole,
  type UserSearchResult,
} from '@/api/globalRbac'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'

export function RolesTab() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [editRole, setEditRole] = useState<GlobalRole | null>(null)
  const [assignOpen, setAssignOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedPerms, setSelectedPerms] = useState<string[]>([])
  const [formError, setFormError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([])
  const [selectedUser, setSelectedUser] = useState<UserSearchResult | null>(null)
  const [userRoles, setUserRoles] = useState<{ id: number; name: string }[]>([])
  const [assignRoleId, setAssignRoleId] = useState<number | null>(null)

  const { data: rolesData } = useQuery({
    queryKey: ['global-roles'],
    queryFn: listGlobalRoles,
  })

  const { data: permsData } = useQuery({
    queryKey: ['global-permissions'],
    queryFn: listGlobalPermissions,
  })

  const createMutation = useMutation({
    mutationFn: () => createGlobalRole({ name, description, permissions: selectedPerms }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['global-roles'] })
      notify('success', tr('Rolle erstellt', 'Role created'), name)
      setCreateOpen(false)
      setName('')
      setDescription('')
      setSelectedPerms([])
      setFormError('')
    },
    onError: (err: Error) => setFormError(err.message),
  })

  const updateMutation = useMutation({
    mutationFn: (role: GlobalRole) => updateGlobalRole(role.id, { permissions: selectedPerms }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['global-roles'] })
      notify('success', tr('Rolle gespeichert', 'Role updated'), editRole?.name)
      setEditRole(null)
      setSelectedPerms([])
    },
    onError: (err: Error) => setFormError(err.message),
  })

  const assignMutation = useMutation({
    mutationFn: () => {
      if (!selectedUser || !assignRoleId) throw new Error(tr('Person oder Rolle fehlt', 'Missing user or role'))
      return assignUserRole(selectedUser.id, assignRoleId)
    },
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['global-roles'] })
      if (selectedUser) {
        const data = await getUserRoles(selectedUser.id)
        setUserRoles(data.roles)
      }
      notify('success', tr('Rolle zugewiesen', 'Role assigned'))
      setAssignRoleId(null)
    },
    onError: (err: Error) => notify('error', tr('Zuweisen fehlgeschlagen', 'Assign failed'), err.message),
  })

  const removeMutation = useMutation({
    mutationFn: ({ userId, roleId }: { userId: number; roleId: number }) =>
      removeUserRole(userId, roleId),
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['global-roles'] })
      if (selectedUser) {
        const data = await getUserRoles(selectedUser.id)
        setUserRoles(data.roles)
      }
      notify('success', tr('Rolle entfernt', 'Role removed'))
    },
    onError: (err: Error) => notify('error', tr('Entfernen fehlgeschlagen', 'Remove failed'), err.message),
  })

  const roles = rolesData?.roles ?? []
  const permissions = permsData?.permissions ?? []

  const handleSearch = async () => {
    if (searchQuery.trim().length < 2) return
    const data = await searchUsers(searchQuery.trim())
    setSearchResults(data.users)
  }

  const handleSelectUser = async (user: UserSearchResult) => {
    setSelectedUser(user)
    const data = await getUserRoles(user.id)
    setUserRoles(data.roles)
  }

  const openEdit = (role: GlobalRole) => {
    setEditRole(role)
    setSelectedPerms(role.permissions)
    setFormError('')
  }

  const togglePerm = (key: string) => {
    setSelectedPerms((prev) =>
      prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key],
    )
  }

  return (
    <div>
      <Group justify="flex-end" mb="md">
        <Group gap={8}>
          <Button
            variant="default"
            leftSection={<IconUserPlus size={16} />}
            onClick={() => {
              setAssignOpen(true)
              setSelectedUser(null)
              setSearchResults([])
              setSearchQuery('')
              setUserRoles([])
            }}
          >
            {tr('Rolle zuweisen', 'Assign role')}
          </Button>
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => {
              setCreateOpen(true)
              setName('')
              setDescription('')
              setSelectedPerms([])
              setFormError('')
            }}
          >
            {tr('Rolle erstellen', 'Create role')}
          </Button>
        </Group>
      </Group>

      <Paper withBorder style={{ overflow: 'hidden' }}>
        <Table.ScrollContainer minWidth={680}>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{tr('Rolle', 'Role')}</Table.Th>
              <Table.Th>{tr('Beschreibung', 'Description')}</Table.Th>
              <Table.Th>{tr('Berechtigungen', 'Permissions')}</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {roles.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={4} ta="center" c="dimmed" py="xl">
                  {tr('Noch keine Plattform-Rollen.', 'No platform roles yet.')}
                </Table.Td>
              </Table.Tr>
            )}
            {roles.map((role) => (
              <Table.Tr key={role.id}>
                <Table.Td fw={600}>
                  {role.name}
                  {role.is_system && (
                    <Badge variant="light" color="gray" size="sm" ml={6}>
                      {tr('System', 'System')}
                    </Badge>
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {role.description ?? '–'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {role.permissions.slice(0, 4).map((p) => (
                      <Badge key={p} variant="light" color="gray" size="sm">
                        {p}
                      </Badge>
                    ))}
                    {role.permissions.length > 4 && (
                      <Text size="xs" c="dimmed">
                        {tr(`+${role.permissions.length - 4} weitere`, `+${role.permissions.length - 4} more`)}
                      </Text>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Button size="xs" variant="default" onClick={() => openEdit(role)}>
                    {tr('Bearbeiten', 'Edit')}
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      </Paper>

      <Modal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        title={tr('Plattform-Rolle erstellen', 'Create platform role')}
        size="lg"
      >
        <Stack gap={16}>
          {formError && (
            <Alert color="red" variant="light">
              {formError}
            </Alert>
          )}
          <TextInput
            label={tr('Name der Rolle', 'Role name')}
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={tr('z. B. Support', 'e.g. Support agent')}
          />
          <TextInput
            label={tr('Beschreibung', 'Description')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={tr('Optional', 'Optional')}
          />
          <Text fw={600} size="sm">
            {tr('Berechtigungen', 'Permissions')}
          </Text>
          <Stack gap={6}>
            {permissions.map((p) => (
              <Checkbox
                key={p.key}
                label={`${p.display_name} (${p.key})`}
                description={p.description ?? undefined}
                checked={selectedPerms.includes(p.key)}
                onChange={() => togglePerm(p.key)}
              />
            ))}
          </Stack>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setCreateOpen(false)}>
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button loading={createMutation.isPending} onClick={() => createMutation.mutate()}>
              {tr('Erstellen', 'Create')}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={!!editRole}
        onClose={() => {
          setEditRole(null)
          setSelectedPerms([])
        }}
        title={tr(`Rolle bearbeiten: ${editRole?.name}`, `Edit role: ${editRole?.name}`)}
        size="lg"
      >
        <Stack gap={16}>
          {formError && (
            <Alert color="red" variant="light">
              {formError}
            </Alert>
          )}
          <Text fw={600} size="sm">
            {tr('Berechtigungen', 'Permissions')}
          </Text>
          <Stack gap={6}>
            {permissions.map((p) => (
              <Checkbox
                key={p.key}
                label={`${p.display_name} (${p.key})`}
                description={p.description ?? undefined}
                checked={selectedPerms.includes(p.key)}
                onChange={() => togglePerm(p.key)}
                disabled={editRole?.is_system && editRole?.name === 'Platform admin'}
              />
            ))}
          </Stack>
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => {
                setEditRole(null)
                setSelectedPerms([])
              }}
            >
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button
              loading={updateMutation.isPending}
              onClick={() => editRole && updateMutation.mutate(editRole)}
            >
              {tr('Speichern', 'Save')}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={assignOpen}
        onClose={() => setAssignOpen(false)}
        title={tr('Rolle einer Person zuweisen', 'Assign a role to a person')}
        size="md"
      >
        <Stack gap={16}>
          <Group gap={8}>
            <TextInput
              placeholder={tr('Nach E-Mail suchen …', 'Search by email…')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              style={{ flex: 1 }}
            />
            <Button variant="default" onClick={handleSearch}>
              {tr('Suchen', 'Search')}
            </Button>
          </Group>

          {searchResults.length > 0 && !selectedUser && (
            <Stack gap={4}>
              {searchResults.map((u) => (
                <Paper
                  key={u.id}
                  withBorder
                  p="sm"
                  onClick={() => handleSelectUser(u)}
                  style={{ cursor: 'pointer' }}
                >
                  <Text fw={600} size="sm">
                    {u.email}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {u.name}
                  </Text>
                </Paper>
              ))}
            </Stack>
          )}

          {selectedUser && (
            <>
              <Paper withBorder p="sm">
                <Text fw={600} size="sm">
                  {selectedUser.email}
                </Text>
                <Text size="xs" c="dimmed">
                  {selectedUser.name}
                </Text>
              </Paper>

              <Text fw={600} size="sm">
                {tr('Aktuelle Rollen', 'Current roles')}
              </Text>
              <Stack gap={4}>
                {userRoles.length === 0 && (
                  <Text size="sm" c="dimmed">
                    {tr('Keine Rollen zugewiesen.', 'No roles assigned.')}
                  </Text>
                )}
                {userRoles.map((r) => (
                  <Group key={r.id} justify="space-between">
                    <Badge variant="light" color="acc" size="sm">
                      {r.name}
                    </Badge>
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={() =>
                        removeMutation.mutate({ userId: selectedUser.id, roleId: r.id })
                      }
                    >
                      {tr('Entfernen', 'Remove')}
                    </Button>
                  </Group>
                ))}
              </Stack>

              <Group gap={8}>
                <Select
                  placeholder={tr('Rolle wählen …', 'Select a role…')}
                  value={assignRoleId ? String(assignRoleId) : null}
                  onChange={(v) => setAssignRoleId(v ? Number(v) : null)}
                  data={roles.map((r) => ({ value: String(r.id), label: r.name }))}
                  style={{ flex: 1 }}
                />
                <Button
                  loading={assignMutation.isPending}
                  disabled={!assignRoleId}
                  onClick={() => assignMutation.mutate()}
                >
                  {tr('Zuweisen', 'Assign')}
                </Button>
              </Group>
            </>
          )}
        </Stack>
      </Modal>
    </div>
  )
}
