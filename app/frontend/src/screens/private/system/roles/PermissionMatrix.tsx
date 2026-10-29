import { Fragment } from 'react'
import { IconShield, IconPencil, IconLock, IconChevronRight } from '@tabler/icons-react'
import { Table, Paper } from '@mantine/core'
import { useT } from '@/locales/i18n'
import type { Role } from '@/api/settings'
import { type PermissionEntry } from '@/api/system'
import { roleLabel } from '@/roles'

import { SectionToggle } from './PermissionControls'
import { blueprintLabel } from './labels'

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
  } = props
  const { t } = useT()
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
                      color: role.isAdmin ? '#3a1e78' : role.isDefault ? '#7441e0' : '#5e5873',
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
                  {role.isAdmin && <IconLock size={11} style={{ color: '#3a1e78' }} />}
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
                      const hasAll = allKeys.every((k) => roleSet?.has(k))
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
                                      color: '#2e2940',
                                    }}
                                  >
                                    <div style={{ fontWeight: 600 }}>{perm.display_name}</div>
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
                                    <Table.Td key={role.id} style={{ textAlign: 'center' }}>
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
                                          accentColor: role.isAdmin ? '#3a1e78' : '#7441e0',
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
                                          color: '#2e2940',
                                        }}
                                      >
                                        <div style={{ fontWeight: 600 }}>{perm.display_name}</div>
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
                                            style={{
                                              width: 16,
                                              height: 16,
                                              accentColor: role.isAdmin ? '#3a1e78' : '#7441e0',
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
                                    <div style={{ fontWeight: 600 }}>{perm.display_name}</div>
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
                                    style={{
                                      width: 16,
                                      height: 16,
                                      accentColor: role.isAdmin ? '#3a1e78' : '#7441e0',
                                      cursor: role.isAdmin ? 'default' : 'pointer',
                                    }}
                                  />
                                </Table.Td>
                              ))}
                            </Table.Tr>
                          ))}
                          {isExpanded &&
                            fieldItems.map((perm) => (
                              <Table.Tr key={perm.key} style={{ background: '#fdfcfe' }}>
                                <Table.Td
                                  style={{
                                    paddingLeft: 56,
                                    color: '#2e2940',
                                  }}
                                >
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
                                      style={{
                                        width: 14,
                                        height: 14,
                                        accentColor: role.isAdmin ? '#3a1e78' : '#7441e0',
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
