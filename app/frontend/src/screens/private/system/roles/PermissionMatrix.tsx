import { Fragment } from 'react'
import { IconShield, IconPencil, IconLock, IconChevronRight } from '@tabler/icons-react'
import { Table, Paper } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useAuth } from '@/context/AppContext'
import type { Role } from '@/api/settings'
import { type PermissionEntry } from '@/api/system'
import { roleDescription, roleLabel } from '@/roles'

import { SectionToggle } from './PermissionControls'
import { blueprintLabel, permLabel, resourceLabel } from './labels'

interface PermissionMatrixProps {
  visibleRoles: Role[]
  allPerms: PermissionEntry[]
  filteredGroups: [string, PermissionEntry[]][]
  settingsNsGroups: [string, PermissionEntry[]][]
  rolePerms: Record<string, Set<string>>
  canSetPermissions: boolean
  canUpdate: boolean
  canDelete: boolean
  expandedResources: Set<string>
  toggleResourceExpand: (resource: string) => void
  toggle: (role: Role, key: string) => void
  toggleAllInScope: (role: Role, keys: string[], on: boolean) => void
  openEdit: (role: Role) => void
  handleDeleteRole: (role: Role) => void
  openMembers: (role: Role) => void
}

/** Roles across the top, one row per permission of the chosen area. */
export function PermissionMatrix(props: PermissionMatrixProps) {
  const {
    visibleRoles,
    allPerms,
    filteredGroups,
    settingsNsGroups,
    rolePerms,
    canSetPermissions,
    canUpdate,
    canDelete,
    expandedResources,
    toggleResourceExpand,
    toggle,
    toggleAllInScope,
    openEdit,
    handleDeleteRole,
    openMembers,
  } = props
  const { t } = useT()
  const { isAdmin } = useAuth()
  // Only an admin changes an admin role; system roles keep their name.
  const mayEdit = (role: Role) => canUpdate && !role.isOwner && (!role.isAdmin || isAdmin)
  const mayDelete = (role: Role) =>
    canDelete && !role.isSystem && !role.isDefault && (!role.isAdmin || isAdmin)
  return (
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
              <Table.Th key={role.id} style={{ textAlign: 'center', minWidth: 100 }}>
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
                      color: role.isAdmin ? 'var(--mantine-color-acc-9)' : role.isDefault ? 'var(--mantine-color-acc-text)' : 'var(--hb-text-2)',
                    }}
                  />
                  <span title={roleDescription(role) || undefined}>{roleLabel(role.name)}</span>
                  {role.isAdmin && (
                    <span
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        fontWeight: 600,
                        color: 'var(--mantine-color-acc-9)',
                        background: '#eef2ff',
                        borderRadius: 4,
                        padding: '1px 6px',
                      }}
                    >
                      ADMIN
                    </span>
                  )}
                  {role.isSystem && <IconLock size={11} style={{ color: 'var(--mantine-color-acc-9)' }} />}
                  {mayEdit(role) && (
                    <button
                      onClick={() => openEdit(role)}
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--hb-text-3)',
                        padding: 0,
                        lineHeight: 1,
                      }}
                      title={`Edit ${role.name}`}
                    >
                      <IconPencil size={11} />
                    </button>
                  )}
                  {mayDelete(role) && (
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
                <button
                  onClick={() => openMembers(role)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--hb-text-2)',
                    fontSize: 'var(--mantine-font-size-xs)',
                    padding: 0,
                    display: 'block',
                    margin: '2px auto 0',
                  }}
                >
                  {t('roles.holderCount', '{{count}} Mitglieder', { count: role.memberCount })}
                </button>
                {role.isAdmin || !canSetPermissions ? null : (
                  <button
                    onClick={() => {
                      const allKeys = allPerms.map((p) => p.key)
                      const roleSet = rolePerms[role.id]
                      const hasAll = allKeys.every((k) => roleSet?.has(k))
                      toggleAllInScope(role, allKeys, !hasAll)
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--hb-text-2)',
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
                      color: 'var(--hb-text-3)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      padding: '10px 16px',
                    }}
                  >
                    <span>{blueprintLabel(bp)}</span>
                  </Table.Td>
                  {visibleRoles.map((role) => (
                    <Table.Td key={role.id} style={{ textAlign: 'center' }}>
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
                        <Table.Tr style={{ background: 'var(--hb-surface-2)' }}>
                          <Table.Td
                            style={{
                              fontWeight: 600,
                              fontSize: 'var(--mantine-font-size-xs)',
                              color: 'var(--hb-text-3)',
                              padding: '6px 16px 6px 36px',
                              borderBottom: '1px solid var(--hb-border)',
                            }}
                          >
                            <span>-- {resourceLabel(ns)} --</span>
                          </Table.Td>
                          {visibleRoles.map((role) => (
                            <Table.Td
                              key={role.id}
                              style={{
                                textAlign: 'center',
                                borderBottom: '1px solid var(--hb-border)',
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
                          const nsLevel = nsPerms.filter((p) => p.key.split('.').length === 3)
                          const keyLevel = nsPerms.filter((p) => p.key.split('.').length > 3)
                          const keyGroups: Record<string, PermissionEntry[]> = {}
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
                                      color: 'var(--hb-text)',
                                    }}
                                  >
                                    <div style={{ fontWeight: 600 }}>{permLabel(perm)}</div>
                                    <div
                                      style={{
                                        fontSize: 'var(--mantine-font-size-xs)',
                                        color: 'var(--hb-text-3)',
                                        fontFamily: "'JetBrains Mono', monospace",
                                      }}
                                    >
                                      {perm.key}
                                    </div>
                                  </Table.Td>
                                  {visibleRoles.map((role) => (
                                    <Table.Td key={role.id} style={{ textAlign: 'center' }}>
                                      <input
                                        type="checkbox"
                                        checked={
                                          role.isAdmin ||
                                          (rolePerms[role.id]?.has(perm.key) ?? false)
                                        }
                                        onChange={() => toggle(role, perm.key)}
                                        disabled={role.isAdmin || !canSetPermissions}
                                        title={role.isAdmin ? t('roles.adminLocked', 'Admin-Rollen haben alle Rechte; die einzelnen Berechtigungen gelten für sie nicht.') : undefined}
                                        style={{
                                          width: 16,
                                          height: 16,
                                          accentColor: role.isAdmin ? 'var(--mantine-color-acc-9)' : 'var(--mantine-color-acc-6)',
                                          cursor: role.isAdmin ? 'default' : 'pointer',
                                        }}
                                      />
                                    </Table.Td>
                                  ))}
                                </Table.Tr>
                              ))}
                              {Object.entries(keyGroups).map(([kn, perms]) => (
                                <Fragment key={kn}>
                                  {perms.map((perm) => (
                                    <Table.Tr key={perm.key}>
                                      <Table.Td
                                        style={{
                                          paddingLeft: 64,
                                          color: 'var(--hb-text)',
                                        }}
                                      >
                                        <div style={{ fontWeight: 600 }}>{permLabel(perm)}</div>
                                        <div
                                          style={{
                                            fontSize: 'var(--mantine-font-size-xs)',
                                            color: 'var(--hb-text-3)',
                                            fontFamily: "'JetBrains Mono', monospace",
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
                                              (rolePerms[role.id]?.has(perm.key) ?? false)
                                            }
                                            onChange={() => toggle(role, perm.key)}
                                            disabled={role.isAdmin || !canSetPermissions}
                                            title={role.isAdmin ? t('roles.adminLocked', 'Admin-Rollen haben alle Rechte; die einzelnen Berechtigungen gelten für sie nicht.') : undefined}
                                            style={{
                                              width: 16,
                                              height: 16,
                                              accentColor: role.isAdmin ? 'var(--mantine-color-acc-9)' : 'var(--mantine-color-acc-6)',
                                              cursor: role.isAdmin ? 'default' : 'pointer',
                                            }}
                                          />
                                        </Table.Td>
                                      ))}
                                    </Table.Tr>
                                  ))}
                                </Fragment>
                              ))}
                            </>
                          )
                        })()}
                      </Fragment>
                    ))
                  : (() => {
                      const coarseItems = items.filter((p) => !p.action.startsWith('update.'))
                      const fieldItems = items.filter((p) => p.action.startsWith('update.'))
                      const resource = coarseItems[0]?.resource || ''
                      const expandKey = `${bp}:${resource}`
                      const hasFields = fieldItems.length > 0
                      const isExpanded = expandedResources.has(expandKey)
                      return (
                        <>
                          {coarseItems.map((perm) => (
                            <Table.Tr key={perm.key}>
                              <Table.Td
                                style={{
                                  paddingLeft: 28,
                                  color: 'var(--hb-text)',
                                }}
                              >
                                <div
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 6,
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
                                        color: 'var(--hb-text-2)',
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
                                          transform: isExpanded ? 'rotate(90deg)' : 'none',
                                          transition: 'transform .15s',
                                        }}
                                      />
                                    </button>
                                  )}
                                  <div>
                                    <div style={{ fontWeight: 600 }}>{permLabel(perm)}</div>
                                    <div
                                      style={{
                                        fontSize: 'var(--mantine-font-size-xs)',
                                        color: 'var(--hb-text-3)',
                                        fontFamily: "'JetBrains Mono', monospace",
                                      }}
                                    >
                                      {perm.key}
                                    </div>
                                  </div>
                                </div>
                              </Table.Td>
                              {visibleRoles.map((role) => (
                                <Table.Td key={role.id} style={{ textAlign: 'center' }}>
                                  <input
                                    type="checkbox"
                                    checked={
                                      role.isAdmin || (rolePerms[role.id]?.has(perm.key) ?? false)
                                    }
                                    onChange={() => toggle(role, perm.key)}
                                    disabled={role.isAdmin || !canSetPermissions}
                                    title={role.isAdmin ? t('roles.adminLocked', 'Admin-Rollen haben alle Rechte; die einzelnen Berechtigungen gelten für sie nicht.') : undefined}
                                    style={{
                                      width: 16,
                                      height: 16,
                                      accentColor: role.isAdmin ? 'var(--mantine-color-acc-9)' : 'var(--mantine-color-acc-6)',
                                      cursor: role.isAdmin ? 'default' : 'pointer',
                                    }}
                                  />
                                </Table.Td>
                              ))}
                            </Table.Tr>
                          ))}
                          {isExpanded &&
                            fieldItems.map((perm) => (
                              <Table.Tr key={perm.key} style={{ background: 'var(--hb-surface-2)' }}>
                                <Table.Td
                                  style={{
                                    paddingLeft: 56,
                                    color: 'var(--hb-text)',
                                  }}
                                >
                                  <div
                                    style={{
                                      fontWeight: 500,
                                      fontSize: 'var(--mantine-font-size-sm)',
                                    }}
                                  >
                                    {permLabel(perm)}
                                  </div>
                                  <div
                                    style={{
                                      fontSize: 'var(--mantine-font-size-xs)',
                                      color: 'var(--hb-text-3)',
                                      fontFamily: "'JetBrains Mono', monospace",
                                    }}
                                  >
                                    {perm.key}
                                  </div>
                                </Table.Td>
                                {visibleRoles.map((role) => (
                                  <Table.Td key={role.id} style={{ textAlign: 'center' }}>
                                    <input
                                      type="checkbox"
                                      checked={
                                        role.isAdmin || (rolePerms[role.id]?.has(perm.key) ?? false)
                                      }
                                      onChange={() => toggle(role, perm.key)}
                                      disabled={role.isAdmin || !canSetPermissions}
                                      title={role.isAdmin ? t('roles.adminLocked', 'Admin-Rollen haben alle Rechte; die einzelnen Berechtigungen gelten für sie nicht.') : undefined}
                                      style={{
                                        width: 14,
                                        height: 14,
                                        accentColor: role.isAdmin ? 'var(--mantine-color-acc-9)' : 'var(--mantine-color-acc-6)',
                                        cursor: role.isAdmin ? 'default' : 'pointer',
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
  )
}
