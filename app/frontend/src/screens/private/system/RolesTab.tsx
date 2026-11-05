import { useState, useMemo, useEffect } from 'react'
import { useMediaQuery } from '@mantine/hooks'
import { IconPlus, IconTemplate, IconUsers, IconGridDots, IconList } from '@tabler/icons-react'
import { Button, MultiSelect, Select, Group, Stack, SegmentedControl } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useToast, useAuth } from '@/context/AppContext'
import { LoadingSpinner } from '@/components/ui'
import type { Role } from '@/api/settings'
import { type PermissionEntry } from '@/api/system'
import { type RoleTemplate } from '@/data/roleTemplates'
import { roleLabel } from '@/roles'
import { RolesOverview } from './roles/RolesOverview'
import { MobilePermissionList } from './roles/MobilePermissionList'
import { PermissionMatrix } from './roles/PermissionMatrix'
import { ResourceMatrix } from './roles/ResourceMatrix'
import { RoleFormModal } from './roles/RoleFormModal'
import { RoleMembersModal } from './roles/RoleMembersModal'
import { TemplatesModal } from './roles/TemplatesModal'
import { blueprintLabel } from './roles/labels'
import { useRoles, type RoleInput } from './roles/useRoles'

export function RolesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const isMobile = useMediaQuery('(max-width: 48em)')
  const canCreate = hasPermission('roles.roles.create')
  const canUpdate = hasPermission('roles.roles.update')
  const canDelete = hasPermission('roles.roles.delete')
  const canSetPermissions = hasPermission('roles.roles.set_permissions')
  // Giving a role changes the member, so it takes the member right.
  const canAssign =
    hasPermission('members.members.update') || hasPermission('members.members.update.role_ids')
  const { roles, allPerms, rolePerms, isLoading: loading, ...rolesApi } = useRoles()
  // 'new' opens the form for a new role, a role opens it for that role.
  const [formRole, setFormRole] = useState<Role | 'new' | null>(null)
  const [selectedNamespace, setSelectedNamespace] = useState('')
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([])
  const [mobileSelectedRoleId, setMobileSelectedRoleId] = useState<string>('')
  const [expandedResources, setExpandedResources] = useState<Set<string>>(
    new Set(),
  )
  // 'roles': one role at a time in levels; the tables compare roles key by key.
  const [page, setPage] = useState<'roles' | 'compare'>('roles')
  const [viewMode, setViewMode] = useState<'permission' | 'resource'>(
    'permission',
  )
  const [templateOpen, setTemplateOpen] = useState(false)
  const [applyingTemplate, setApplyingTemplate] = useState(false)
  const [roleMembersOpen, setRoleMembersOpen] = useState<Role | null>(null)

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


  const fail = (title: string) => (err: unknown) =>
    notify('error', title, err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'))

  const handleApplyTemplate = async (template: RoleTemplate) => {
    setApplyingTemplate(true)
    try {
      await rolesApi.applyTemplate(template)
      setTemplateOpen(false)
      notify(
        'success',
        t('roles.templateApplied', 'Vorlage angewendet'),
        t('roles.templateAppliedMsg', 'Die Vorlage «{{name}}» wurde angewendet: {{count}} Rollen eingerichtet.', { name: template.name, count: template.roles.length }),
      )
    } catch (err: unknown) {
      fail(t('roles.templateFailed', 'Vorlage fehlgeschlagen'))(err)
    } finally {
      setApplyingTemplate(false)
    }
  }

  const toggle = (role: Role, key: string) => {
    if (role.isAdmin) return
    rolesApi.togglePerm(role, key).catch(fail(t('roles.permFailed', 'Berechtigung konnte nicht geändert werden')))
  }

  const toggleAllInScope = (role: Role, keys: string[], on: boolean) => {
    if (role.isAdmin) return
    rolesApi.setPerms(role, keys, on).catch(fail(t('roles.permFailed', 'Berechtigung konnte nicht geändert werden')))
  }

  const setArea = (role: Role, area: PermissionEntry[], keys: string[]) => {
    if (role.isAdmin) return
    rolesApi
      .setAreaPerms(role, area.map((p) => p.key), keys)
      .catch(fail(t('roles.permFailed', 'Berechtigung konnte nicht geändert werden')))
  }

  const handleCreateRole = async (input: RoleInput) => {
    try {
      await rolesApi.create(input)
      setFormRole(null)
      notify(
        'success',
        t('roles.created', 'Rolle erstellt'),
        t('roles.createdMsg', 'Die Rolle «{{name}}» ist bereit. Lege unten ihre Berechtigungen fest.', { name: input.name }),
      )
    } catch (err: unknown) {
      fail(t('common.createFailed', 'Erstellen fehlgeschlagen'))(err)
    }
  }

  const handleDeleteRole = async (role: Role) => {
    try {
      await rolesApi.remove(role)
      notify('info', t('roles.removed', 'Rolle entfernt'), t('roles.removedMsg', '«{{name}}» wurde gelöscht.', { name: role.name }))
    } catch (err: unknown) {
      fail(t('common.deleteFailed', 'Löschen fehlgeschlagen'))(err)
    }
  }

  const openEdit = (role: Role) => setFormRole(role)

  const handleSaveEdit = async (role: Role, input: RoleInput) => {
    try {
      const updated = await rolesApi.save(role, input)
      setFormRole(null)
      notify('success', t('roles.updated', 'Rolle gespeichert'), t('roles.updatedMsg', '«{{name}}» wurde gespeichert.', { name: updated.name }))
    } catch (err: unknown) {
      fail(t('common.updateFailed', 'Aktualisieren fehlgeschlagen'))(err)
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
      <Group justify="space-between" mb={16} className="page-actions">
        <SegmentedControl
          value={page}
          onChange={(v) => setPage(v as 'roles' | 'compare')}
          data={[
            { value: 'roles', label: t('roles.pageRoles', 'Rollen') },
            { value: 'compare', label: t('roles.pageCompare', 'Vergleichen') },
          ]}
        />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {canCreate && (
            <Button variant="default" onClick={() => setTemplateOpen(true)}>
              <IconTemplate size={16} />
              {t('roles.templates', 'Vorlagen')}
            </Button>
          )}
          {canCreate && (
            <Button variant="default" onClick={() => setFormRole('new')}>
              <IconPlus size={16} />
              {t('roles.new', 'Neue Rolle')}
            </Button>
          )}
        </div>
      </Group>
      {page === 'roles' && (
        <RolesOverview
          roles={roles}
          allPerms={allPerms}
          rolePerms={rolePerms}
          canUpdate={canUpdate}
          canDelete={canDelete}
          canSetPermissions={canSetPermissions}
          canAssign={canAssign}
          onEdit={openEdit}
          onDelete={handleDeleteRole}
          onToggle={toggle}
          onSetKeys={setArea}
        />
      )}
      {page === 'compare' && (
        <>
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
            {roles.length > 0 && (
              <Button
                variant="subtle"
                size="xs"
                onClick={() => {
                  const first = visibleRoles[0] ?? roles[0]
                  if (first) setRoleMembersOpen(first)
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
                        (r.isAdmin ? ' (Admin)' : r.isSystem ? ' (System)' : ''),
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
                        (r.isAdmin ? ' (Admin)' : r.isSystem ? ' (System)' : ''),
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
                <PermissionMatrix
                  visibleRoles={visibleRoles}
                  allPerms={allPerms}
                  filteredGroups={filteredGroups}
                  settingsNsGroups={settingsNsGroups}
                  rolePerms={rolePerms}
                  canSetPermissions={canSetPermissions}
                  canUpdate={canUpdate}
                  canDelete={canDelete}
                  expandedResources={expandedResources}
                  toggleResourceExpand={toggleResourceExpand}
                  toggle={toggle}
                  toggleAllInScope={toggleAllInScope}
                  openEdit={openEdit}
                  handleDeleteRole={handleDeleteRole}
                  openMembers={setRoleMembersOpen}
                />
              )}
            </>
          )}

          {viewMode === 'resource' && (
            <ResourceMatrix
              visibleRoles={visibleRoles}
              allPerms={allPerms}
              rolePerms={rolePerms}
              canSetPermissions={canSetPermissions}
              toggle={toggle}
              toggleAllInScope={toggleAllInScope}
            />
          )}
        </>
      )}

      <RoleFormModal
        key={formRole === 'new' ? 'new' : (formRole?.id ?? 'closed')}
        open={formRole !== null}
        role={formRole === 'new' ? null : formRole}
        onClose={() => setFormRole(null)}
        onSubmit={formRole === 'new' || formRole === null ? handleCreateRole : (input) => handleSaveEdit(formRole, input)}
      />
      <TemplatesModal
        open={templateOpen}
        onClose={() => setTemplateOpen(false)}
        onApply={handleApplyTemplate}
        applying={applyingTemplate}
      />
      <RoleMembersModal
        role={roleMembersOpen}
        roles={roles}
        canAssign={canAssign}
        onRoleChange={setRoleMembersOpen}
        onClose={() => setRoleMembersOpen(null)}
      />
    </div>
  )
}
