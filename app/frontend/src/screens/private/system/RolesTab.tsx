import { useState, useMemo, useEffect, Fragment } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMediaQuery } from '@mantine/hooks'
import {
  IconPlus,
  IconShield,
  IconPencil,
  IconLock,
  IconChevronRight,
  IconTemplate,
  IconUsers,
  IconGridDots,
  IconList,
  IconSearch,
} from '@tabler/icons-react'
import {
  Table,
  TextInput,
  Button,
  Paper,
  MultiSelect,
  Select,
  Group,
  Stack,
  Text,
  SegmentedControl,
  Badge,
  ScrollArea,
  Checkbox,
  Alert,
} from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useToast, useAuth } from '@/context/AppContext'
import { Modal, Field, LoadingSpinner } from '@/components/ui'
import {
  listRoles,
  createRole,
  updateRole,
  deleteRole,
  getRolePermissions,
  setRolePermissions,
} from '@/api/settings'
import type { Role } from '@/api/settings'
import { getSystemPermissions, type PermissionEntry } from '@/api/system'
import { updateMember } from '@/api/members'
import { useMemberSearch } from '@/data/members'
import { qk } from '@/data/keys'
import type { Member } from '@/types'
import { ROLE_TEMPLATES, type RoleTemplate } from '@/data/roleTemplates'
import { roleLabel } from '@/roles'

function SectionToggle({
  role,
  keys,
  roleSet,
  onToggle,
  canSetPermissions,
}: {
  role: Role
  keys: string[]
  roleSet: Set<string> | undefined
  onToggle: (role: Role, keys: string[], on: boolean) => void
  canSetPermissions: boolean
}) {
  const allSelected = keys.length > 0 && keys.every((k) => roleSet?.has(k))
  const someSelected = !allSelected && keys.some((k) => roleSet?.has(k))
  const disabled = role.isAdmin || !canSetPermissions
  return (
    <input
      type="checkbox"
      checked={role.isAdmin || allSelected}
      ref={(el) => {
        if (el) el.indeterminate = role.isAdmin ? false : someSelected
      }}
      onChange={() => onToggle(role, keys, !allSelected)}
      disabled={disabled}
      style={{
        width: 14,
        height: 14,
        accentColor: role.isAdmin ? '#3a1e78' : '#7441e0',
        cursor: disabled ? 'default' : 'pointer',
      }}
    />
  )
}

function blueprintLabel(bp: string): string {
  const stripped = bp.replace(/_bp$/, '')
  return stripped.charAt(0).toUpperCase() + stripped.slice(1)
}

function PermCheckbox({
  role,
  permKey,
  roleSet,
  onToggle,
  canSetPermissions,
  size = 18,
}: {
  role: Role
  permKey: string
  roleSet: Set<string> | undefined
  onToggle: (role: Role, key: string) => void
  canSetPermissions: boolean
  size?: number
}) {
  const disabled = role.isAdmin || !canSetPermissions
  return (
    <input
      type="checkbox"
      checked={role.isAdmin || (roleSet?.has(permKey) ?? false)}
      onChange={() => onToggle(role, permKey)}
      disabled={disabled}
      style={{
        width: size,
        height: size,
        flexShrink: 0,
        marginTop: 2,
        accentColor: role.isAdmin ? '#3a1e78' : '#7441e0',
        cursor: disabled ? 'default' : 'pointer',
      }}
    />
  )
}

function MobilePermissionList({
  role,
  groupedPerms,
  settingsNsGroups,
  roleSet,
  onToggle,
  onToggleAll,
  canSetPermissions,
  expandedResources,
  toggleResourceExpand,
}: {
  role: Role
  groupedPerms: [string, PermissionEntry[]][]
  settingsNsGroups: [string, PermissionEntry[]][]
  roleSet: Set<string> | undefined
  onToggle: (role: Role, key: string) => void
  onToggleAll: (role: Role, keys: string[], on: boolean) => void
  canSetPermissions: boolean
  expandedResources: Set<string>
  toggleResourceExpand: (resource: string) => void
}) {
  const { t } = useT()
  return (
    <Stack gap={10}>
      {groupedPerms.map(([bp, items]) => {
        const isSettings = bp === 'settings_bp' || bp === 'settings'
        return (
          <Paper
            key={bp}
            withBorder
            radius="md"
            p={0}
            style={{ overflow: 'hidden' }}
          >
            <Group
              justify="space-between"
              px={16}
              py={10}
              style={{
                borderBottom: '1px solid #e6e3ef',
                background: '#f9f8fc',
                alignItems: 'center',
              }}
            >
              <Text
                fz="xs"
                fw={700}
                c="#857f99"
                tt="uppercase"
                style={{ letterSpacing: '0.06em' }}
              >
                {blueprintLabel(bp)}
              </Text>
              <SectionToggle
                role={role}
                keys={items.map((p) => p.key)}
                roleSet={roleSet}
                onToggle={onToggleAll}
                canSetPermissions={canSetPermissions}
              />
            </Group>

            {isSettings && settingsNsGroups.length > 0
              ? settingsNsGroups.map(([ns, nsPerms]) => {
                  const nsLevel = nsPerms.filter(
                    (p) => p.key.split('.').length === 3,
                  )
                  const keyLevel = nsPerms.filter(
                    (p) => p.key.split('.').length > 3,
                  )
                  const keyGroups: Record<string, PermissionEntry[]> = {}
                  for (const p of keyLevel) {
                    const parts = p.key.split('.')
                    const kn = parts.slice(2, -1).join('.')
                    if (!keyGroups[kn]) keyGroups[kn] = []
                    keyGroups[kn].push(p)
                  }
                  return (
                    <div key={ns}>
                      <Group
                        justify="space-between"
                        px={16}
                        py={7}
                        style={{
                          background: '#fdfcfe',
                          borderBottom: '1px solid #e6e3ef',
                          alignItems: 'center',
                        }}
                      >
                        <Text fz="xs" fw={600} c="#8c86a0">
                          {ns}
                        </Text>
                        <SectionToggle
                          role={role}
                          keys={nsPerms.map((p) => p.key)}
                          roleSet={roleSet}
                          onToggle={onToggleAll}
                          canSetPermissions={canSetPermissions}
                        />
                      </Group>
                      {nsLevel.map((perm) => (
                        <Group
                          key={perm.key}
                          gap={12}
                          px={16}
                          py={10}
                          style={{
                            borderBottom: '1px solid #f1eff7',
                            alignItems: 'flex-start',
                          }}
                        >
                          <PermCheckbox
                            role={role}
                            permKey={perm.key}
                            roleSet={roleSet}
                            onToggle={onToggle}
                            canSetPermissions={canSetPermissions}
                          />
                          <div>
                            <div
                              style={{
                                fontWeight: 600,
                                fontSize: 'var(--mantine-font-size-sm)',
                              }}
                            >
                              {perm.display_name}
                            </div>
                            <div
                              style={{
                                fontSize: 'var(--mantine-font-size-xs)',
                                color: '#8c86a0',
                                fontFamily: "'JetBrains Mono', monospace",
                              }}
                            >
                              {perm.key}
                            </div>
                          </div>
                        </Group>
                      ))}
                      {Object.entries(keyGroups).map(([kn, perms]) => (
                        <Fragment key={kn}>
                          {perms.map((perm) => (
                            <Group
                              key={perm.key}
                              gap={12}
                              px={16}
                              py={8}
                              style={{
                                borderBottom: '1px solid #f1eff7',
                                alignItems: 'flex-start',
                                paddingLeft: 32,
                              }}
                            >
                              <PermCheckbox
                                role={role}
                                permKey={perm.key}
                                roleSet={roleSet}
                                onToggle={onToggle}
                                canSetPermissions={canSetPermissions}
                                size={16}
                              />
                              <div>
                                <div
                                  style={{
                                    fontWeight: 500,
                                    fontSize: 'var(--mantine-font-size-sm)',
                                  }}
                                >
                                  {perm.display_name}
                                </div>
                                <div
                                  style={{
                                    fontSize: 'var(--mantine-font-size-xs)',
                                    color: '#8c86a0',
                                    fontFamily: "'JetBrains Mono', monospace",
                                  }}
                                >
                                  {perm.key}
                                </div>
                              </div>
                            </Group>
                          ))}
                        </Fragment>
                      ))}
                    </div>
                  )
                })
              : (() => {
                  const coarseItems = items.filter(
                    (p) => !p.action.startsWith('update.'),
                  )
                  const fieldItems = items.filter((p) =>
                    p.action.startsWith('update.'),
                  )
                  const resource = coarseItems[0]?.resource || ''
                  const expandKey = `${bp}:${resource}`
                  const hasFields = fieldItems.length > 0
                  const isExpanded = expandedResources.has(expandKey)
                  return (
                    <>
                      {coarseItems.map((perm) => (
                        <Group
                          key={perm.key}
                          gap={12}
                          px={16}
                          py={10}
                          style={{
                            borderBottom: '1px solid #f1eff7',
                            alignItems: 'flex-start',
                          }}
                        >
                          {perm.action === 'update' && hasFields && (
                            <button
                              onClick={() => toggleResourceExpand(expandKey)}
                              style={{
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                padding: 0,
                                display: 'flex',
                                alignItems: 'center',
                                color: '#5e5873',
                                flexShrink: 0,
                                marginTop: 2,
                              }}
                              title={
                                isExpanded
                                  ? t('roles.hideFields', 'Feldrechte ausblenden')
                                  : t('roles.showFields', 'Feldrechte anzeigen')
                              }
                            >
                              <IconChevronRight
                                size={16}
                                style={{
                                  transform: isExpanded
                                    ? 'rotate(90deg)'
                                    : 'none',
                                  transition: 'transform .15s',
                                }}
                              />
                            </button>
                          )}
                          <PermCheckbox
                            role={role}
                            permKey={perm.key}
                            roleSet={roleSet}
                            onToggle={onToggle}
                            canSetPermissions={canSetPermissions}
                          />
                          <div style={{ flex: 1 }}>
                            <div
                              style={{
                                fontWeight: 600,
                                fontSize: 'var(--mantine-font-size-sm)',
                              }}
                            >
                              {perm.display_name}
                            </div>
                            <div
                              style={{
                                fontSize: 'var(--mantine-font-size-xs)',
                                color: '#8c86a0',
                                fontFamily: "'JetBrains Mono', monospace",
                              }}
                            >
                              {perm.key}
                            </div>
                          </div>
                        </Group>
                      ))}
                      {isExpanded &&
                        fieldItems.map((perm) => (
                          <Group
                            key={perm.key}
                            gap={12}
                            px={16}
                            py={8}
                            style={{
                              borderBottom: '1px solid #f1eff7',
                              alignItems: 'flex-start',
                              paddingLeft: 40,
                              background: '#fdfcfe',
                            }}
                          >
                            <PermCheckbox
                              role={role}
                              permKey={perm.key}
                              roleSet={roleSet}
                              onToggle={onToggle}
                              canSetPermissions={canSetPermissions}
                              size={16}
                            />
                            <div>
                              <div
                                style={{
                                  fontWeight: 500,
                                  fontSize: 'var(--mantine-font-size-sm)',
                                }}
                              >
                                {perm.display_name}
                              </div>
                              <div
                                style={{
                                  fontSize: 'var(--mantine-font-size-xs)',
                                  color: '#8c86a0',
                                  fontFamily: "'JetBrains Mono', monospace",
                                }}
                              >
                                {perm.key}
                              </div>
                            </div>
                          </Group>
                        ))}
                    </>
                  )
                })()}
          </Paper>
        )
      })}
    </Stack>
  )
}

export function RolesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const isMobile = useMediaQuery('(max-width: 48em)')
  const canCreate = hasPermission('roles.roles.create')
  const canUpdate = hasPermission('roles.roles.update')
  const canDelete = hasPermission('roles.roles.delete')
  const canSetPermissions = hasPermission('roles.roles.set_permissions')
  const [localPerms, setLocalPerms] = useState<Record<string, Set<string>>>({})
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Role | null>(null)
  const [newRoleName, setNewRoleName] = useState('')
  const [newRoleDesc, setNewRoleDesc] = useState('')
  const [newRoleIsAdmin, setNewRoleIsAdmin] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [editIsAdmin, setEditIsAdmin] = useState(false)
  const [selectedNamespace, setSelectedNamespace] = useState('')
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([])
  const [mobileSelectedRoleId, setMobileSelectedRoleId] = useState<string>('')
  const [expandedResources, setExpandedResources] = useState<Set<string>>(
    new Set(),
  )
  const [viewMode, setViewMode] = useState<'permission' | 'resource'>(
    'permission',
  )
  const [templateOpen, setTemplateOpen] = useState(false)
  const [applyingTemplate, setApplyingTemplate] = useState(false)
  const [roleMembersOpen, setRoleMembersOpen] = useState<Role | null>(null)

  const { data, isLoading: loading } = useQuery({
    queryKey: ['roles-permissions'],
    queryFn: async () => {
      const [roleList, perms] = await Promise.all([
        listRoles(),
        getSystemPermissions(),
      ])
      const permsMap: Record<string, Set<string>> = {}
      for (const role of roleList) {
        const permissions = await getRolePermissions(role.id)
        permsMap[role.id] = new Set(permissions)
      }
      return { roles: roleList, allPerms: perms, rolePerms: permsMap }
    },
    staleTime: Infinity,
  })
  const roles = useMemo(() => data?.roles ?? [], [data?.roles])
  const allPerms = useMemo(() => data?.allPerms ?? [], [data?.allPerms])
  const rolePerms = useMemo(() => {
    const base = data?.rolePerms ?? {}
    const merged: Record<string, Set<string>> = {}
    for (const roleId of Object.keys(base)) {
      merged[roleId] = localPerms[roleId] ?? base[roleId]
    }
    for (const roleId of Object.keys(localPerms)) {
      if (!merged[roleId]) merged[roleId] = localPerms[roleId]
    }
    return merged
  }, [data?.rolePerms, localPerms])

  const [roleMemberSearch, setRoleMemberSearch] = useState('')
  const { data: memberPage } = useMemberSearch(roleMemberSearch, { enabled: !!roleMembersOpen })
  const membersData = memberPage?.members

  const groupedPerms = useMemo(() => {
    const seen = new Map<string, PermissionEntry>()
    for (const p of allPerms) {
      if (!seen.has(p.key)) seen.set(p.key, p)
    }
    const groups: Record<string, PermissionEntry[]> = {}
    for (const p of seen.values()) {
      const bp = p.blueprint || 'other'
      if (!groups[bp]) groups[bp] = []
      groups[bp].push(p)
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }, [allPerms])

  const settingsNsGroups = useMemo(() => {
    const nsMap: Record<string, PermissionEntry[]> = {}
    for (const p of allPerms) {
      if (p.blueprint !== 'settings_bp' && p.blueprint !== 'settings') continue
      const ns = p.resource || 'other'
      if (!nsMap[ns]) nsMap[ns] = []
      nsMap[ns].push(p)
    }
    return Object.entries(nsMap).sort(([a], [b]) => a.localeCompare(b))
  }, [allPerms])

  const namespaces = useMemo(() => {
    const set = new Set<string>()
    for (const p of allPerms) {
      set.add(p.blueprint || 'other')
    }
    return Array.from(set).sort()
  }, [allPerms])

  useEffect(() => {
    if (!selectedNamespace && namespaces.length > 0) {
      queueMicrotask(() => setSelectedNamespace(namespaces[0]))
    }
  }, [namespaces, selectedNamespace])

  useEffect(() => {
    if (roles.length > 0 && selectedRoleIds.length === 0) {
      queueMicrotask(() =>
        setSelectedRoleIds(roles.filter((r) => !r.isAdmin).map((r) => r.id)),
      )
    }
  }, [roles, selectedRoleIds.length])

  useEffect(() => {
    if (roles.length > 0 && !mobileSelectedRoleId) {
      const first = roles.find((r) => !r.isAdmin) ?? roles[0]
      if (first) queueMicrotask(() => setMobileSelectedRoleId(first.id))
    }
  }, [roles, mobileSelectedRoleId])

  const mobileSelectedRole = useMemo(
    () => roles.find((r) => r.id === mobileSelectedRoleId) ?? null,
    [roles, mobileSelectedRoleId],
  )

  const visibleRoles = useMemo(
    () => roles.filter((r) => selectedRoleIds.includes(r.id)),
    [roles, selectedRoleIds],
  )

  const filteredGroups = useMemo(() => {
    if (!selectedNamespace) return []
    return groupedPerms.filter(
      ([bp]) => bp === selectedNamespace || bp === selectedNamespace + '_bp',
    )
  }, [groupedPerms, selectedNamespace])

  const toggleResourceExpand = (resource: string) => {
    setExpandedResources((prev) => {
      const next = new Set(prev)
      if (next.has(resource)) next.delete(resource)
      else next.add(resource)
      return next
    })
  }

  const resourceActionMatrix = useMemo(() => {
    const resources: Record<
      string,
      {
        blueprint: string
        resource: string
        actions: Map<string, PermissionEntry>
      }
    > = {}
    for (const p of allPerms) {
      if (p.action.startsWith('update.')) continue
      const key = `${p.blueprint}:${p.resource}`
      if (!resources[key]) {
        resources[key] = {
          blueprint: p.blueprint,
          resource: p.resource,
          actions: new Map(),
        }
      }
      resources[key].actions.set(p.action, p)
    }
    return Object.entries(resources)
      .map(([key, val]) => ({ key, ...val }))
      .sort((a, b) =>
        `${a.blueprint}.${a.resource}`.localeCompare(
          `${b.blueprint}.${b.resource}`,
        ),
      )
  }, [allPerms])

  const handleApplyTemplate = async (template: RoleTemplate) => {
    setApplyingTemplate(true)
    try {
      for (const templateRole of template.roles) {
        const existing = roles.find((r) => r.name === templateRole.name)
        let roleId: string
        if (existing) {
          roleId = existing.id
          if (
            templateRole.description &&
            existing.description !== templateRole.description
          ) {
            await updateRole(roleId, {
              name: templateRole.name,
              description: templateRole.description,
              is_admin: templateRole.is_admin,
            })
          }
        } else {
          const created = await createRole(
            templateRole.name,
            templateRole.description,
          )
          roleId = created.id
          if (templateRole.is_admin) {
            await updateRole(roleId, {
              name: templateRole.name,
              description: templateRole.description,
              is_admin: true,
            })
          }
        }
        if (!templateRole.is_admin && templateRole.permissions.length > 0) {
          await setRolePermissions(roleId, templateRole.permissions)
        }
      }
      await queryClient.invalidateQueries({ queryKey: ['roles-permissions'] })
      queryClient.invalidateQueries({ queryKey: ['lookups'] })
      setTemplateOpen(false)
      notify(
        'success',
        t('roles.templateApplied', 'Vorlage angewendet'),
        t('roles.templateAppliedMsg', 'Die Vorlage «{{name}}» wurde angewendet: {{count}} Rollen eingerichtet.', { name: template.name, count: template.roles.length }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('roles.templateFailed', 'Vorlage fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setApplyingTemplate(false)
    }
  }

  const handleToggleRoleMembership = async (
    member: Member,
    role: Role,
    add: boolean,
  ) => {
    const currentRoles = member.roles ?? []
    const newRoles = add
      ? [...currentRoles, role.name]
      : currentRoles.filter((r) => r !== role.name)
    try {
      await updateMember(member.id, { roleNames: newRoles })
      queryClient.invalidateQueries({ queryKey: qk.members.all })
    } catch (err: unknown) {
      notify(
        'error',
        t('roles.assignFailed', 'Rolle konnte nicht zugewiesen werden'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const toggle = (role: Role, key: string) => {
    if (role.isAdmin) return
    const base = rolePerms[role.id] ?? new Set<string>()
    const next = new Set(base)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setLocalPerms((prev) => ({ ...prev, [role.id]: next }))
    setRolePermissions(role.id, Array.from(next)).catch((err: unknown) => {
      setLocalPerms((prev) => ({ ...prev, [role.id]: base }))
      notify(
        'error',
        t('roles.permFailed', 'Berechtigung konnte nicht geändert werden'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    })
  }

  const toggleAllInScope = (role: Role, keys: string[], on: boolean) => {
    if (role.isAdmin) return
    const base = rolePerms[role.id] ?? new Set<string>()
    const next = new Set(base)
    for (const key of keys) {
      if (on) next.add(key)
      else next.delete(key)
    }
    setLocalPerms((prev) => ({ ...prev, [role.id]: next }))
    setRolePermissions(role.id, Array.from(next)).catch((err: unknown) => {
      setLocalPerms((prev) => ({ ...prev, [role.id]: base }))
      notify(
        'error',
        t('roles.permFailed', 'Berechtigung konnte nicht geändert werden'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    })
  }

  const handleCreateRole = async () => {
    const name = newRoleName.trim()
    if (!name) return
    try {
      const newRole = await createRole(name, newRoleDesc.trim() || null)
      if (newRoleIsAdmin) {
        const updated = await updateRole(newRole.id, {
          name,
          description: newRoleDesc.trim() || null,
          is_admin: true,
        })
        queryClient.setQueryData<{
          roles: Role[]
          allPerms: PermissionEntry[]
          rolePerms: Record<string, Set<string>>
        }>(['roles-permissions'], (old) => {
          if (!old) return old
          return {
            ...old,
            roles: [...old.roles, updated],
            rolePerms: { ...old.rolePerms, [updated.id]: new Set() },
          }
        })
      } else {
        queryClient.setQueryData<{
          roles: Role[]
          allPerms: PermissionEntry[]
          rolePerms: Record<string, Set<string>>
        }>(['roles-permissions'], (old) => {
          if (!old) return old
          return {
            ...old,
            roles: [...old.roles, newRole],
            rolePerms: { ...old.rolePerms, [newRole.id]: new Set() },
          }
        })
      }
      queryClient.invalidateQueries({ queryKey: ['lookups'] })
      setNewRoleName('')
      setNewRoleDesc('')
      setNewRoleIsAdmin(false)
      setAddOpen(false)
      notify(
        'success',
        t('roles.created', 'Rolle erstellt'),
        t('roles.createdMsg', 'Die Rolle «{{name}}» ist bereit. Lege unten ihre Berechtigungen fest.', { name }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.createFailed', 'Erstellen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const handleDeleteRole = async (role: Role) => {
    try {
      await deleteRole(role.id)
      queryClient.setQueryData<{
        roles: Role[]
        allPerms: PermissionEntry[]
        rolePerms: Record<string, Set<string>>
      }>(['roles-permissions'], (old) => {
        if (!old) return old
        const nextPerms = { ...old.rolePerms }
        delete nextPerms[role.id]
        return {
          ...old,
          roles: old.roles.filter((r) => r.id !== role.id),
          rolePerms: nextPerms,
        }
      })
      queryClient.invalidateQueries({ queryKey: ['lookups'] })
      setLocalPerms((prev) => {
        const next = { ...prev }
        delete next[role.id]
        return next
      })
      notify('info', t('roles.removed', 'Rolle entfernt'), t('roles.removedMsg', '«{{name}}» wurde gelöscht.', { name: role.name }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const openEdit = (role: Role) => {
    setEditTarget(role)
    setEditName(role.name)
    setEditDesc(role.description ?? '')
    setEditIsAdmin(role.isAdmin)
  }

  const handleSaveEdit = async () => {
    if (!editTarget) return
    try {
      const updated = await updateRole(editTarget.id, {
        name: editName.trim(),
        description: editDesc.trim() || null,
        is_admin: editIsAdmin,
      })
      queryClient.setQueryData<{
        roles: Role[]
        allPerms: PermissionEntry[]
        rolePerms: Record<string, Set<string>>
      }>(['roles-permissions'], (old) => {
        if (!old) return old
        return {
          ...old,
          roles: old.roles.map((r) => (r.id === updated.id ? updated : r)),
        }
      })
      queryClient.invalidateQueries({ queryKey: ['lookups'] })
      setEditTarget(null)
      notify('success', t('roles.updated', 'Rolle gespeichert'), t('roles.updatedMsg', '«{{name}}» wurde gespeichert.', { name: updated.name }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.updateFailed', 'Aktualisieren fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  if (loading) {
    return (
      <div>
        <LoadingSpinner compact message={t('common.loading', 'Wird geladen …')} />
      </div>
    )
  }

  return (
    <div>
      <Group justify="flex-end" mb={16} className="page-actions">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {canCreate && (
            <Button variant="default" onClick={() => setTemplateOpen(true)}>
              <IconTemplate size={16} />
              {t('roles.templates', 'Vorlagen')}
            </Button>
          )}
          {canCreate && (
            <Button variant="default" onClick={() => setAddOpen(true)}>
              <IconPlus size={16} />
              {t('roles.new', 'Neue Rolle')}
            </Button>
          )}
        </div>
      </Group>
      <Group justify="space-between" mb={12} align="center">
        <SegmentedControl
          size="xs"
          value={viewMode}
          onChange={(v) => setViewMode(v as 'permission' | 'resource')}
          data={[
            {
              value: 'permission',
              label: (
                <Group gap={4} wrap="nowrap">
                  <IconList size={14} />
                  {t('roles.byPermission', 'Nach Berechtigung')}
                </Group>
              ),
            },
            {
              value: 'resource',
              label: (
                <Group gap={4} wrap="nowrap">
                  <IconGridDots size={14} />
                  {t('roles.byResource', 'Nach Bereich')}
                </Group>
              ),
            },
          ]}
        />
        {canUpdate && (
          <Button
            variant="subtle"
            size="xs"
            onClick={() => {
              if (visibleRoles.length > 0) setRoleMembersOpen(visibleRoles[0])
            }}
          >
            <IconUsers size={14} />
            {t('roles.members', 'Rollenmitglieder')}
          </Button>
        )}
      </Group>
      {viewMode === 'permission' && (
        <>
          {isMobile ? (
            <Stack gap={12} mb={16}>
              <Select
                label={t('roles.role', 'Rolle')}
                data={roles.map((r) => ({
                  value: r.id,
                  label:
                    roleLabel(r.name) +
                    (r.isAdmin ? ' (Admin)' : r.isDefault ? ' (System)' : ''),
                }))}
                value={mobileSelectedRoleId}
                onChange={(v) => v && setMobileSelectedRoleId(v)}
                searchable
                size="sm"
              />
              <Select
                label={t('roles.namespace', 'Bereich')}
                data={namespaces.map((ns) => ({
                  value: ns,
                  label: blueprintLabel(ns),
                }))}
                value={selectedNamespace}
                onChange={(v) => v && setSelectedNamespace(v)}
                searchable
                size="sm"
              />
            </Stack>
          ) : (
            <Group gap={12} mb={16} grow align="flex-end">
              <Select
                label={t('roles.namespace', 'Bereich')}
                data={namespaces.map((ns) => ({
                  value: ns,
                  label: blueprintLabel(ns),
                }))}
                value={selectedNamespace}
                onChange={(v) => v && setSelectedNamespace(v)}
                searchable
                size="sm"
              />
              <MultiSelect
                label={t('common.roles', 'Rollen')}
                data={roles.map((r) => ({
                  value: r.id,
                  label:
                    roleLabel(r.name) +
                    (r.isAdmin ? ' (Admin)' : r.isDefault ? ' (System)' : ''),
                }))}
                value={selectedRoleIds}
                onChange={setSelectedRoleIds}
                placeholder={t('roles.selectDisplay', 'Rollen zur Anzeige wählen')}
                searchable
                clearable
                hidePickedOptions
                size="sm"
              />
            </Group>
          )}
          {isMobile && mobileSelectedRole ? (
            <MobilePermissionList
              role={mobileSelectedRole}
              groupedPerms={filteredGroups}
              settingsNsGroups={settingsNsGroups}
              roleSet={rolePerms[mobileSelectedRole.id]}
              onToggle={toggle}
              onToggleAll={toggleAllInScope}
              canSetPermissions={canSetPermissions}
              expandedResources={expandedResources}
              toggleResourceExpand={toggleResourceExpand}
            />
          ) : (
            <Paper
              withBorder
              shadow="sm"
              radius="lg"
              className="table-matrix-wrap"
              style={{ overflowX: 'auto' }}
            >
              <Table highlightOnHover style={{ minWidth: 560 }}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th style={{ minWidth: 160 }}>{t('roles.permission', 'Berechtigung')}</Table.Th>
                    {visibleRoles.map((role) => (
                      <Table.Th
                        key={role.id}
                        style={{ textAlign: 'center', minWidth: 100 }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 6,
                          }}
                        >
                          <IconShield
                            size={16}
                            style={{
                              color: role.isAdmin
                                ? '#3a1e78'
                                : role.isDefault
                                  ? '#7441e0'
                                  : '#5e5873',
                            }}
                          />
                          {roleLabel(role.name)}
                          {role.isAdmin && (
                            <span
                              style={{
                                fontSize: 'var(--mantine-font-size-xs)',
                                fontWeight: 600,
                                color: '#3a1e78',
                                background: '#eef2ff',
                                borderRadius: 4,
                                padding: '1px 6px',
                              }}
                            >
                              ADMIN
                            </span>
                          )}
                          {role.isAdmin && (
                            <IconLock size={11} style={{ color: '#3a1e78' }} />
                          )}
                          {canUpdate && !role.isAdmin && (
                            <button
                              onClick={() => openEdit(role)}
                              style={{
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                color: '#8c86a0',
                                padding: 0,
                                lineHeight: 1,
                              }}
                              title={`Edit ${role.name}`}
                            >
                              <IconPencil size={11} />
                            </button>
                          )}
                          {!role.isDefault && !role.isAdmin && canDelete && (
                            <button
                              onClick={() => handleDeleteRole(role)}
                              style={{
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                color: '#ff4d3d',
                                padding: 0,
                                lineHeight: 1,
                              }}
                              title={`Delete ${role.name}`}
                            >
                              {'\u2715'}
                            </button>
                          )}
                        </div>
                        {role.isAdmin || !canSetPermissions ? null : (
                          <button
                            onClick={() => {
                              const allKeys = allPerms.map((p) => p.key)
                              const roleSet = rolePerms[role.id]
                              const hasAll = allKeys.every(
                                (k) => roleSet?.has(k),
                              )
                              toggleAllInScope(role, allKeys, !hasAll)
                            }}
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              color: '#5e5873',
                              textDecoration: 'underline',
                              fontSize: 'var(--mantine-font-size-xs)',
                              padding: 0,
                              marginTop: 4,
                            }}
                          >
                            {(() => {
                              const allKeys = allPerms.map((p) => p.key)
                              const roleSet = rolePerms[role.id]
                              return allKeys.every((k) => roleSet?.has(k))
                                ? t('roles.deselectAll', 'Alle abwählen')
                                : t('roles.selectAll', 'Alle wählen')
                            })()}
                          </button>
                        )}
                      </Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {filteredGroups.map(([bp, items]) => {
                    const isSettings = bp === 'settings_bp' || bp === 'settings'
                    return (
                      <Fragment key={bp}>
                        <Table.Tr style={{ background: '#f9f8fc' }}>
                          <Table.Td
                            style={{
                              fontWeight: 700,
                              fontSize: 'var(--mantine-font-size-xs)',
                              color: '#857f99',
                              textTransform: 'uppercase',
                              letterSpacing: '0.06em',
                              padding: '10px 16px',
                            }}
                          >
                            <span>{blueprintLabel(bp)}</span>
                          </Table.Td>
                          {visibleRoles.map((role) => (
                            <Table.Td
                              key={role.id}
                              style={{ textAlign: 'center' }}
                            >
                              <SectionToggle
                                role={role}
                                keys={items.map((p) => p.key)}
                                roleSet={rolePerms[role.id]}
                                onToggle={toggleAllInScope}
                                canSetPermissions={canSetPermissions}
                              />
                            </Table.Td>
                          ))}
                        </Table.Tr>
                        {isSettings && settingsNsGroups.length > 0
                          ? settingsNsGroups.map(([ns, nsPerms]) => (
                              <Fragment key={ns}>
                                <Table.Tr style={{ background: '#fdfcfe' }}>
                                  <Table.Td
                                    style={{
                                      fontWeight: 600,
                                      fontSize: 'var(--mantine-font-size-xs)',
                                      color: '#8c86a0',
                                      padding: '6px 16px 6px 36px',
                                      borderBottom: '1px solid #e6e3ef',
                                    }}
                                  >
                                    <span>-- {ns} --</span>
                                  </Table.Td>
                                  {visibleRoles.map((role) => (
                                    <Table.Td
                                      key={role.id}
                                      style={{
                                        textAlign: 'center',
                                        borderBottom: '1px solid #e6e3ef',
                                      }}
                                    >
                                      <SectionToggle
                                        role={role}
                                        keys={nsPerms.map((p) => p.key)}
                                        roleSet={rolePerms[role.id]}
                                        onToggle={toggleAllInScope}
                                        canSetPermissions={canSetPermissions}
                                      />
                                    </Table.Td>
                                  ))}
                                </Table.Tr>
                                {(() => {
                                  const nsLevel = nsPerms.filter(
                                    (p) => p.key.split('.').length === 3,
                                  )
                                  const keyLevel = nsPerms.filter(
                                    (p) => p.key.split('.').length > 3,
                                  )
                                  const keyGroups: Record<
                                    string,
                                    PermissionEntry[]
                                  > = {}
                                  for (const p of keyLevel) {
                                    const parts = p.key.split('.')
                                    const kn = parts.slice(2, -1).join('.')
                                    if (!keyGroups[kn]) keyGroups[kn] = []
                                    keyGroups[kn].push(p)
                                  }
                                  return (
                                    <>
                                      {nsLevel.map((perm) => (
                                        <Table.Tr key={perm.key}>
                                          <Table.Td
                                            style={{
                                              paddingLeft: 48,
                                              color: '#2e2940',
                                            }}
                                          >
                                            <div style={{ fontWeight: 600 }}>
                                              {perm.display_name}
                                            </div>
                                            <div
                                              style={{
                                                fontSize:
                                                  'var(--mantine-font-size-xs)',
                                                color: '#8c86a0',
                                                fontFamily:
                                                  "'JetBrains Mono', monospace",
                                              }}
                                            >
                                              {perm.key}
                                            </div>
                                          </Table.Td>
                                          {visibleRoles.map((role) => (
                                            <Table.Td
                                              key={role.id}
                                              style={{ textAlign: 'center' }}
                                            >
                                              <input
                                                type="checkbox"
                                                checked={
                                                  role.isAdmin ||
                                                  (rolePerms[role.id]?.has(
                                                    perm.key,
                                                  ) ??
                                                    false)
                                                }
                                                onChange={() =>
                                                  toggle(role, perm.key)
                                                }
                                                disabled={
                                                  role.isAdmin ||
                                                  !canSetPermissions
                                                }
                                                style={{
                                                  width: 16,
                                                  height: 16,
                                                  accentColor: role.isAdmin
                                                    ? '#3a1e78'
                                                    : '#7441e0',
                                                  cursor: role.isAdmin
                                                    ? 'default'
                                                    : 'pointer',
                                                }}
                                              />
                                            </Table.Td>
                                          ))}
                                        </Table.Tr>
                                      ))}
                                      {Object.entries(keyGroups).map(
                                        ([kn, perms]) => (
                                          <Fragment key={kn}>
                                            {perms.map((perm) => (
                                              <Table.Tr key={perm.key}>
                                                <Table.Td
                                                  style={{
                                                    paddingLeft: 64,
                                                    color: '#2e2940',
                                                  }}
                                                >
                                                  <div
                                                    style={{ fontWeight: 600 }}
                                                  >
                                                    {perm.display_name}
                                                  </div>
                                                  <div
                                                    style={{
                                                      fontSize:
                                                        'var(--mantine-font-size-xs)',
                                                      color: '#8c86a0',
                                                      fontFamily:
                                                        "'JetBrains Mono', monospace",
                                                    }}
                                                  >
                                                    {perm.key}
                                                  </div>
                                                </Table.Td>
                                                {visibleRoles.map((role) => (
                                                  <Table.Td
                                                    key={role.id}
                                                    style={{
                                                      textAlign: 'center',
                                                    }}
                                                  >
                                                    <input
                                                      type="checkbox"
                                                      checked={
                                                        role.isAdmin ||
                                                        (rolePerms[
                                                          role.id
                                                        ]?.has(perm.key) ??
                                                          false)
                                                      }
                                                      onChange={() =>
                                                        toggle(role, perm.key)
                                                      }
                                                      disabled={
                                                        role.isAdmin ||
                                                        !canSetPermissions
                                                      }
                                                      style={{
                                                        width: 16,
                                                        height: 16,
                                                        accentColor:
                                                          role.isAdmin
                                                            ? '#3a1e78'
                                                            : '#7441e0',
                                                        cursor: role.isAdmin
                                                          ? 'default'
                                                          : 'pointer',
                                                      }}
                                                    />
                                                  </Table.Td>
                                                ))}
                                              </Table.Tr>
                                            ))}
                                          </Fragment>
                                        ),
                                      )}
                                    </>
                                  )
                                })()}
                              </Fragment>
                            ))
                          : (() => {
                              const coarseItems = items.filter(
                                (p) => !p.action.startsWith('update.'),
                              )
                              const fieldItems = items.filter((p) =>
                                p.action.startsWith('update.'),
                              )
                              const resource = coarseItems[0]?.resource || ''
                              const expandKey = `${bp}:${resource}`
                              const hasFields = fieldItems.length > 0
                              const isExpanded =
                                expandedResources.has(expandKey)
                              return (
                                <>
                                  {coarseItems.map((perm) => (
                                    <Table.Tr key={perm.key}>
                                      <Table.Td
                                        style={{
                                          paddingLeft: 28,
                                          color: '#2e2940',
                                        }}
                                      >
                                        <div
                                          style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 6,
                                          }}
                                        >
                                          {perm.action === 'update' &&
                                            hasFields && (
                                              <button
                                                onClick={() =>
                                                  toggleResourceExpand(
                                                    expandKey,
                                                  )
                                                }
                                                style={{
                                                  background: 'none',
                                                  border: 'none',
                                                  cursor: 'pointer',
                                                  padding: 0,
                                                  display: 'flex',
                                                  alignItems: 'center',
                                                  color: '#5e5873',
                                                }}
                                                title={
                                                  isExpanded
                                                    ? t('roles.hideFields', 'Feldrechte ausblenden')
                                                    : t('roles.showFields', 'Feldrechte anzeigen')
                                                }
                                              >
                                                <IconChevronRight
                                                  size={14}
                                                  style={{
                                                    transform: isExpanded
                                                      ? 'rotate(90deg)'
                                                      : 'none',
                                                    transition:
                                                      'transform .15s',
                                                  }}
                                                />
                                              </button>
                                            )}
                                          <div>
                                            <div style={{ fontWeight: 600 }}>
                                              {perm.display_name}
                                            </div>
                                            <div
                                              style={{
                                                fontSize:
                                                  'var(--mantine-font-size-xs)',
                                                color: '#8c86a0',
                                                fontFamily:
                                                  "'JetBrains Mono', monospace",
                                              }}
                                            >
                                              {perm.key}
                                            </div>
                                          </div>
                                        </div>
                                      </Table.Td>
                                      {visibleRoles.map((role) => (
                                        <Table.Td
                                          key={role.id}
                                          style={{ textAlign: 'center' }}
                                        >
                                          <input
                                            type="checkbox"
                                            checked={
                                              role.isAdmin ||
                                              (rolePerms[role.id]?.has(
                                                perm.key,
                                              ) ??
                                                false)
                                            }
                                            onChange={() =>
                                              toggle(role, perm.key)
                                            }
                                            disabled={
                                              role.isAdmin || !canSetPermissions
                                            }
                                            style={{
                                              width: 16,
                                              height: 16,
                                              accentColor: role.isAdmin
                                                ? '#3a1e78'
                                                : '#7441e0',
                                              cursor: role.isAdmin
                                                ? 'default'
                                                : 'pointer',
                                            }}
                                          />
                                        </Table.Td>
                                      ))}
                                    </Table.Tr>
                                  ))}
                                  {isExpanded &&
                                    fieldItems.map((perm) => (
                                      <Table.Tr
                                        key={perm.key}
                                        style={{ background: '#fdfcfe' }}
                                      >
                                        <Table.Td
                                          style={{
                                            paddingLeft: 56,
                                            color: '#2e2940',
                                          }}
                                        >
                                          <div
                                            style={{
                                              fontWeight: 500,
                                              fontSize:
                                                'var(--mantine-font-size-sm)',
                                            }}
                                          >
                                            {perm.display_name}
                                          </div>
                                          <div
                                            style={{
                                              fontSize:
                                                'var(--mantine-font-size-xs)',
                                              color: '#8c86a0',
                                              fontFamily:
                                                "'JetBrains Mono', monospace",
                                            }}
                                          >
                                            {perm.key}
                                          </div>
                                        </Table.Td>
                                        {visibleRoles.map((role) => (
                                          <Table.Td
                                            key={role.id}
                                            style={{ textAlign: 'center' }}
                                          >
                                            <input
                                              type="checkbox"
                                              checked={
                                                role.isAdmin ||
                                                (rolePerms[role.id]?.has(
                                                  perm.key,
                                                ) ??
                                                  false)
                                              }
                                              onChange={() =>
                                                toggle(role, perm.key)
                                              }
                                              disabled={
                                                role.isAdmin ||
                                                !canSetPermissions
                                              }
                                              style={{
                                                width: 14,
                                                height: 14,
                                                accentColor: role.isAdmin
                                                  ? '#3a1e78'
                                                  : '#7441e0',
                                                cursor: role.isAdmin
                                                  ? 'default'
                                                  : 'pointer',
                                              }}
                                            />
                                          </Table.Td>
                                        ))}
                                      </Table.Tr>
                                    ))}
                                </>
                              )
                            })()}
                      </Fragment>
                    )
                  })}
                </Table.Tbody>
              </Table>
            </Paper>
          )}
        </>
      )}

      {viewMode === 'resource' && (
        <Paper withBorder shadow="sm" radius="lg" style={{ overflowX: 'auto' }}>
          <Table highlightOnHover style={{ minWidth: 520 }}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th style={{ minWidth: 180 }}>{t('roles.resource', 'Bereich')}</Table.Th>
                {visibleRoles.map((role) => (
                  <Table.Th
                    key={role.id}
                    style={{ textAlign: 'center', minWidth: 100 }}
                  >
                    <Group gap={6} justify="center" wrap="nowrap">
                      <IconShield
                        size={14}
                        style={{
                          color: role.isAdmin
                            ? '#3a1e78'
                            : role.isDefault
                              ? '#7441e0'
                              : '#5e5873',
                        }}
                      />
                      <Text size="sm" fw={600}>
                        {roleLabel(role.name)}
                      </Text>
                      {role.isAdmin && (
                        <Badge size="xs" color="indigo" variant="light">
                          ADMIN
                        </Badge>
                      )}
                    </Group>
                  </Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {resourceActionMatrix.map((entry) => {
                const actions = Array.from(entry.actions.entries()).sort(
                  ([a], [b]) => a.localeCompare(b),
                )
                return (
                  <Fragment key={entry.key}>
                    <Table.Tr style={{ background: '#f9f8fc' }}>
                      <Table.Td
                        style={{
                          fontWeight: 700,
                          fontSize: 'var(--mantine-font-size-xs)',
                          color: '#857f99',
                          textTransform: 'uppercase',
                          letterSpacing: '0.06em',
                          padding: '10px 16px',
                        }}
                      >
                        {blueprintLabel(entry.blueprint)} / {entry.resource}
                      </Table.Td>
                      {visibleRoles.map((role) => (
                        <Table.Td key={role.id} style={{ textAlign: 'center' }}>
                          <SectionToggle
                            role={role}
                            keys={actions.map(([, p]) => p.key)}
                            roleSet={rolePerms[role.id]}
                            onToggle={toggleAllInScope}
                            canSetPermissions={canSetPermissions}
                          />
                        </Table.Td>
                      ))}
                    </Table.Tr>
                    {actions.map(([action, perm]) => (
                      <Table.Tr key={perm.key}>
                        <Table.Td
                          style={{
                            paddingLeft: 28,
                            color: '#2e2940',
                          }}
                        >
                          <div
                            style={{
                              fontWeight: 600,
                              display: 'flex',
                              alignItems: 'center',
                              gap: 6,
                            }}
                          >
                            {action}
                          </div>
                          <div
                            style={{
                              fontSize: 'var(--mantine-font-size-xs)',
                              color: '#8c86a0',
                              fontFamily: "'JetBrains Mono', monospace",
                            }}
                          >
                            {perm.key}
                          </div>
                        </Table.Td>
                        {visibleRoles.map((role) => (
                          <Table.Td
                            key={role.id}
                            style={{ textAlign: 'center' }}
                          >
                            <input
                              type="checkbox"
                              checked={
                                role.isAdmin ||
                                (rolePerms[role.id]?.has(perm.key) ?? false)
                              }
                              onChange={() => toggle(role, perm.key)}
                              disabled={role.isAdmin || !canSetPermissions}
                              style={{
                                width: 16,
                                height: 16,
                                accentColor: role.isAdmin
                                  ? '#3a1e78'
                                  : '#7441e0',
                                cursor: role.isAdmin ? 'default' : 'pointer',
                              }}
                            />
                          </Table.Td>
                        ))}
                      </Table.Tr>
                    ))}
                  </Fragment>
                )
              })}
            </Table.Tbody>
          </Table>
        </Paper>
      )}

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('roles.new', 'Neue Rolle')}
        subtitle={t('roles.newSubtitle', 'Startet ohne Berechtigungen. Lege sie danach in der Tabelle fest.')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" onClick={handleCreateRole}>
              {t('roles.create', 'Rolle erstellen')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field label={t('roles.name', 'Name der Rolle')}>
            <TextInput
              placeholder={t('roles.namePlaceholder', 'z. B. Moderation')}
              value={newRoleName}
              onChange={(e) => setNewRoleName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateRole()}
            />
          </Field>
          <Field label={t('common.description', 'Beschreibung')} hint={t('roles.descHint', 'Optional, wird in der Verwaltung angezeigt')}>
            <TextInput
              placeholder={t('roles.descPlaceholder', 'z. B. Darf Mitglieder und Finanzen verwalten')}
              value={newRoleDesc}
              onChange={(e) => setNewRoleDesc(e.target.value)}
            />
          </Field>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 'var(--mantine-font-size-sm)',
              cursor: 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={newRoleIsAdmin}
              onChange={(e) => setNewRoleIsAdmin(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: '#3a1e78' }}
            />
            <span style={{ fontWeight: 600 }}>{t('roles.adminRole', 'Admin-Rolle')}</span>
            <span
              style={{
                color: '#5e5873',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {t('roles.adminHint', 'Umgeht alle Berechtigungsprüfungen')}
            </span>
          </label>
        </div>
      </Modal>

      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('roles.edit', 'Rolle bearbeiten')}
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" onClick={handleSaveEdit}>
              {t('common.saveChanges', 'Änderungen speichern')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field label={t('roles.name', 'Name der Rolle')}>
            <TextInput
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
            />
          </Field>
          <Field label={t('common.description', 'Beschreibung')} hint={t('roles.descHint', 'Optional, wird in der Verwaltung angezeigt')}>
            <TextInput
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
            />
          </Field>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 'var(--mantine-font-size-sm)',
              cursor: 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={editIsAdmin}
              onChange={(e) => setEditIsAdmin(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: '#3a1e78' }}
            />
            <span style={{ fontWeight: 600 }}>{t('roles.adminRole', 'Admin-Rolle')}</span>
            <span
              style={{
                color: '#5e5873',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {t('roles.adminHint', 'Umgeht alle Berechtigungsprüfungen')}
            </span>
          </label>
        </div>
      </Modal>

      <Modal
        open={templateOpen}
        onClose={() => setTemplateOpen(false)}
        title={t('roles.templatesTitle', 'Rollenvorlagen')}
        subtitle={t('roles.templatesSubtitle', 'Wende einen vorbereiteten Satz an Rollen und Berechtigungen an.')}
        wide
      >
        <Stack gap={16}>
          <Alert color="blue" variant="light">
            {t(
              'roles.templateWarning',
              'Eine Vorlage legt fehlende Rollen an und setzt ihre Berechtigungen. Bei bestehenden Rollen mit gleichem Namen werden die Berechtigungen ersetzt.',
            )}
          </Alert>
          {ROLE_TEMPLATES.map((template) => (
            <Paper key={template.id} withBorder p="md" radius="md">
              <Group justify="space-between" align="flex-start">
                <Stack gap={4} style={{ flex: 1 }}>
                  <Text fw={700}>{template.name}</Text>
                  <Text size="sm" c="dimmed">
                    {template.description}
                  </Text>
                  <Group gap={6} mt={4}>
                    {template.roles.map((r) => (
                      <Badge
                        key={r.name}
                        size="sm"
                        color={r.is_admin ? 'indigo' : 'gray'}
                        variant={r.is_admin ? 'light' : 'outline'}
                      >
                        {r.name}
                        {r.is_admin
                          ? ' (admin)'
                          : ` (${r.permissions.length} perms)`}
                      </Badge>
                    ))}
                  </Group>
                </Stack>
                <Button
                  size="sm"
                  variant="default"
                  loading={applyingTemplate}
                  onClick={() => handleApplyTemplate(template)}
                >
                  {t('roles.apply', 'Anwenden')}
                </Button>
              </Group>
            </Paper>
          ))}
        </Stack>
      </Modal>

      <Modal
        open={!!roleMembersOpen}
        onClose={() => setRoleMembersOpen(null)}
        title={t('roles.members', 'Rollenmitglieder')}
        subtitle={
          roleMembersOpen
            ? t('roles.assignTo', 'Mitgliedern die Rolle {{role}} geben', {
                role: roleLabel(roleMembersOpen.name),
              })
            : ''
        }
        wide
      >
        <Stack gap={12}>
          {visibleRoles.length > 0 && (
            <Select
              label={t('roles.role', 'Rolle')}
              data={visibleRoles.map((r) => ({
                value: r.id,
                label: roleLabel(r.name) + (r.isAdmin ? ' (Admin)' : ''),
              }))}
              value={roleMembersOpen?.id ?? ''}
              onChange={(v) => {
                const role = roles.find((r) => r.id === v)
                if (role) setRoleMembersOpen(role)
              }}
              size="sm"
            />
          )}
          {roleMembersOpen && (
            <TextInput
              size="sm"
              leftSection={<IconSearch size={14} />}
              placeholder={t('roles.searchMembers', 'Mitglied suchen …')}
              aria-label={t('roles.searchMembers', 'Mitglied suchen …')}
              value={roleMemberSearch}
              onChange={(e) => setRoleMemberSearch(e.currentTarget.value)}
            />
          )}
          {roleMembersOpen && (
            <ScrollArea.Autosize mah={400} offsetScrollbars>
              <Stack gap={6}>
                {(membersData ?? []).map((member) => {
                  const hasRole = member.roles?.includes(roleMembersOpen.name)
                  return (
                    <Group
                      key={member.id}
                      justify="space-between"
                      p="xs"
                      style={{
                        borderBottom: '1px solid #f1eff7',
                      }}
                    >
                      <Group gap={10}>
                        <div
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: '50%',
                            background: member.avatarColor || '#3a1e78',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#fff',
                            fontWeight: 700,
                            fontSize: 13,
                            flexShrink: 0,
                          }}
                        >
                          {member.firstName[0]}
                          {member.lastName[0]}
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 'sm' }}>
                            {member.name}
                          </div>
                          <div
                            style={{
                              fontSize: 'var(--mantine-font-size-xs)',
                              color: '#8c86a0',
                            }}
                          >
                            {member.email}
                          </div>
                        </div>
                      </Group>
                      <Checkbox
                        checked={hasRole ?? false}
                        disabled={roleMembersOpen.isAdmin}
                        onChange={(e) =>
                          handleToggleRoleMembership(
                            member,
                            roleMembersOpen,
                            e.currentTarget.checked,
                          )
                        }
                        size="sm"
                      />
                    </Group>
                  )
                })}
                {membersData && membersData.length === 0 && (
                  <Text c="dimmed" ta="center" py="lg">
                    {t('roles.noMembers', 'Keine Mitglieder gefunden.')}
                  </Text>
                )}
                {!membersData && (
                  <LoadingSpinner compact message={t('roles.loadingMembers', 'Mitglieder werden geladen …')} />
                )}
              </Stack>
            </ScrollArea.Autosize>
          )}
        </Stack>
      </Modal>
    </div>
  )
}
