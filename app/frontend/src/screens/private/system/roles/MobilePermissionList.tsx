import { Fragment } from 'react'
import { IconChevronRight } from '@tabler/icons-react'
import { Paper, Group, Stack, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import type { Role } from '@/api/settings'
import { type PermissionEntry } from '@/api/system'
import { PermCheckbox, SectionToggle } from './PermissionControls'
import { blueprintLabel } from './labels'

export function MobilePermissionList({
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
          <Paper key={bp} withBorder radius="md" p={0} style={{ overflow: 'hidden' }}>
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
              <Text fz="xs" fw={700} c="#857f99" tt="uppercase" style={{ letterSpacing: '0.06em' }}>
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
                  const coarseItems = items.filter((p) => !p.action.startsWith('update.'))
                  const fieldItems = items.filter((p) => p.action.startsWith('update.'))
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
                                  transform: isExpanded ? 'rotate(90deg)' : 'none',
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
