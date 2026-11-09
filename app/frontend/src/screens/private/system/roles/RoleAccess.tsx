import { Fragment, useMemo, useState } from 'react'
import {
  Alert,
  Badge,
  Group,
  Paper,
  SegmentedControl,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { IconChevronRight, IconShieldCheck } from '@tabler/icons-react'
import type { Role } from '@/api/settings'
import type { PermissionEntry } from '@/api/system'
import { useData } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { localizeModule } from '@/modules/labels'
import { PermCheckbox } from './PermissionControls'
import { blueprintLabel, permLabel, resourceLabel } from './labels'
import {
  currentLevel,
  isAccessKey,
  levelKeys,
  offeredLevels,
  toModuleGroups,
  type Level,
} from './levels'

/**
 * What one role may do, with the levels Keine, Ansehen, Bearbeiten and
 * Alles: one picker per module (Keine hides the module from the role's
 * holders, docs/roles.md), and one line per area inside a module with
 * several. The arrow opens the single permissions for a mix the levels
 * don't cover.
 */
export function RoleAccess({
  role,
  allPerms,
  roleSet,
  canSetPermissions,
  onToggle,
  onSetKeys,
}: {
  role: Role
  allPerms: PermissionEntry[]
  roleSet: Set<string> | undefined
  canSetPermissions: boolean
  onToggle: (role: Role, key: string) => void
  onSetKeys: (role: Role, area: PermissionEntry[], keys: string[]) => void
}) {
  const { t } = useT()
  const { moduleList } = useData()
  const [open, setOpen] = useState<Set<string>>(new Set())
  const groups = useMemo(() => {
    const names: Record<string, string> = {}
    for (const m of moduleList) names[m.code] = localizeModule(m).name
    return toModuleGroups(allPerms)
      .map((g) => ({
        ...g,
        label: g.module ? (names[g.module] ?? blueprintLabel(g.id)) : blueprintLabel(g.id),
      }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [allPerms, moduleList])

  const levelLabel: Record<Level, string> = {
    none: t('roles.level.none', 'Keine'),
    view: t('roles.level.view', 'Ansehen'),
    edit: t('roles.level.edit', 'Bearbeiten'),
    all: t('roles.level.all', 'Alles'),
  }
  const disabled = !canSetPermissions
  const toggleOpen = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  // Admin roles pass every check, so there is nothing to choose.
  if (role.isAdmin) {
    return (
      <Alert color="acc" variant="light" icon={<IconShieldCheck size={18} />}>
        {t('roles.adminAll', 'Diese Rolle ist eine Admin-Rolle und darf im Verein alles.')}
      </Alert>
    )
  }

  return (
    <Stack gap={12}>
      <Text size="sm" c="dimmed">
        {t(
          'roles.levelHint',
          'Keine: das Modul ist für diese Rolle ausgeblendet (eigene Daten bleiben im Profil). Ansehen: sehen und mitmachen (anmelden, abstimmen, kommentieren). Bearbeiten: auch erstellen und ändern. Alles: auch löschen und exportieren.',
        )}
      </Text>
      <Paper withBorder p={0} style={{ overflow: 'hidden' }}>
        {groups.map((group, groupIndex) => {
          const areas = group.areas
          // A module with one area is one line; its picker covers the module.
          const single = areas.length === 1
          const moduleLevel = currentLevel(group.perms, roleSet)
          const moduleOffered = offeredLevels(group.perms)
          const picker = (
            perms: typeof group.perms,
            level: Level | null,
            offered: Level[],
            label: string,
          ) => (
            <SegmentedControl
              size="xs"
              radius="md"
              aria-label={label}
              value={level ?? ''}
              disabled={disabled}
              onChange={(v) => onSetKeys(role, perms, levelKeys(perms, v as Level))}
              data={offered.map((l) => ({ value: l, label: levelLabel[l] }))}
            />
          )
          return (
            <Fragment key={group.id}>
              {!single && (
                <Group
                  justify="space-between"
                  wrap="wrap"
                  gap={8}
                  px="md"
                  py={8}
                  style={{
                    background: 'var(--hb-surface-2)',
                    borderTop: groupIndex > 0 ? '1px solid var(--hb-border)' : undefined,
                  }}
                >
                  <Group gap={6}>
                    <Text
                      size="xs"
                      fw={700}
                      c="dimmed"
                      tt="uppercase"
                      style={{ letterSpacing: '0.06em' }}
                    >
                      {group.label}
                    </Text>
                    {group.hides && moduleLevel === 'none' && (
                      <Badge size="xs" variant="light" color="gray">
                        {t('roles.moduleHidden', 'Ausgeblendet')}
                      </Badge>
                    )}
                  </Group>
                  {/* Modules get one picker for all their areas; core areas
                      without a module keep only their own lines. */}
                  {group.module && picker(group.perms, moduleLevel, moduleOffered, group.label)}
                </Group>
              )}
              {areas.map((area, index) => {
                const perms = single ? group.perms : area.perms
                const offered = offeredLevels(perms)
                const level = currentLevel(perms, roleSet)
                const isOpen = open.has(area.key)
                const name = single
                  ? group.label
                  : area.resource === area.blueprint.replace(/_bp$/, '')
                    ? blueprintLabel(area.blueprint)
                    : resourceLabel(area.resource)
                return (
                  <Fragment key={area.key}>
                    <Group
                      justify="space-between"
                      wrap="wrap"
                      gap={8}
                      pr="md"
                      py={8}
                      pl={single ? 'md' : 'xl'}
                      style={{
                        borderTop:
                          groupIndex === 0 && index === 0 && single
                            ? undefined
                            : '1px solid var(--hb-border)',
                      }}
                    >
                      <UnstyledButton
                        onClick={() => toggleOpen(area.key)}
                        aria-expanded={isOpen}
                        title={
                          isOpen
                            ? t('roles.hideSingle', 'Einzelne Rechte ausblenden')
                            : t('roles.showSingle', 'Einzelne Rechte zeigen')
                        }
                        style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}
                      >
                        <IconChevronRight
                          size={14}
                          style={{
                            color: 'var(--hb-text-3)',
                            transform: isOpen ? 'rotate(90deg)' : 'none',
                            transition: 'transform .15s',
                            flexShrink: 0,
                          }}
                        />
                        <Text fw={600} size="sm">
                          {name}
                        </Text>
                        {level === null && (
                          <Badge size="xs" variant="light" color="orange">
                            {t('roles.level.custom', 'Angepasst')}
                          </Badge>
                        )}
                        {single && group.hides && level === 'none' && (
                          <Badge size="xs" variant="light" color="gray">
                            {t('roles.moduleHidden', 'Ausgeblendet')}
                          </Badge>
                        )}
                      </UnstyledButton>
                      {picker(perms, level, offered, name)}
                    </Group>
                    {isOpen && (
                      <Stack gap={6} pr="md" pb={10} pl={single ? 36 : 52}>
                        {perms.map((perm) => (
                          <label
                            key={perm.key}
                            style={{
                              display: 'flex',
                              gap: 8,
                              alignItems: 'flex-start',
                              cursor: disabled ? 'default' : 'pointer',
                            }}
                            title={perm.key}
                          >
                            <PermCheckbox
                              role={role}
                              permKey={perm.key}
                              roleSet={roleSet}
                              onToggle={onToggle}
                              canSetPermissions={canSetPermissions}
                              size={15}
                            />
                            <Text size="sm">
                              {isAccessKey(perm.key)
                                ? t(
                                    'roles.perms.moduleAccess',
                                    'Modul verwenden (sehen und öffnen)',
                                  )
                                : permLabel(perm)}
                            </Text>
                          </label>
                        ))}
                      </Stack>
                    )}
                  </Fragment>
                )
              })}
            </Fragment>
          )
        })}
      </Paper>
    </Stack>
  )
}
