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
import { useT } from '@/locales/i18n'
import { PermCheckbox } from './PermissionControls'
import { blueprintLabel, permLabel, resourceLabel } from './labels'
import { currentLevel, levelKeys, offeredLevels, toAreas, type Area, type Level } from './levels'

/**
 * What one role may do, one line per area with the levels Keine, Ansehen,
 * Bearbeiten and Alles. "Einzeln" opens the single permissions for a mix
 * the levels don't cover.
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
  const areas = useMemo(() => toAreas(allPerms), [allPerms])
  const [open, setOpen] = useState<Set<string>>(new Set())
  const byBlueprint = useMemo(() => {
    const out = new Map<string, Area[]>()
    for (const area of areas) {
      const list = out.get(area.blueprint) ?? []
      list.push(area)
      out.set(area.blueprint, list)
    }
    return [...out.entries()].sort(([a], [b]) => blueprintLabel(a).localeCompare(blueprintLabel(b)))
  }, [areas])

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
      <Alert color="violet" variant="light" icon={<IconShieldCheck size={18} />}>
        {t('roles.adminAll', 'Diese Rolle ist eine Admin-Rolle und darf im Verein alles.')}
      </Alert>
    )
  }

  return (
    <Stack gap={12}>
      <Text size="sm" c="dimmed">
        {t(
          'roles.levelHint',
          'Ansehen: sehen und mitmachen (anmelden, abstimmen, kommentieren). Bearbeiten: auch erstellen und ändern. Alles: auch löschen und exportieren.',
        )}
      </Text>
      <Paper withBorder radius="lg" p={0} style={{ overflow: 'hidden' }}>
        {byBlueprint.map(([bp, list], bpIndex) => (
          <Fragment key={bp}>
            {/* An area with several parts (Finanzen) gets a heading over them. */}
            {list.length > 1 && (
              <Text
                size="xs"
                fw={700}
                c="dimmed"
                tt="uppercase"
                px="md"
                pt={12}
                pb={6}
                style={{
                  letterSpacing: '0.06em',
                  background: 'var(--hb-surface-2)',
                  borderTop: bpIndex > 0 ? '1px solid var(--hb-border)' : undefined,
                }}
              >
                {blueprintLabel(bp)}
              </Text>
            )}
            {list.map((area, index) => {
              const offered = offeredLevels(area.perms)
              const level = currentLevel(area.perms, roleSet)
              const isOpen = open.has(area.key)
              const name =
                area.resource === bp.replace(/_bp$/, '') || list.length === 1
                  ? blueprintLabel(bp)
                  : resourceLabel(area.resource)
              return (
                <Fragment key={area.key}>
                  <Group
                    justify="space-between"
                    wrap="wrap"
                    gap={8}
                    pr="md"
                    py={8}
                    pl={list.length > 1 ? 'xl' : 'md'}
                    style={{
                      borderTop:
                        bpIndex === 0 && index === 0 && list.length === 1
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
                    </UnstyledButton>
                    <SegmentedControl
                      size="xs"
                      radius="md"
                      value={level ?? ''}
                      disabled={disabled}
                      onChange={(v) =>
                        onSetKeys(role, area.perms, levelKeys(area.perms, v as Level))
                      }
                      data={offered.map((l) => ({ value: l, label: levelLabel[l] }))}
                    />
                  </Group>
                  {isOpen && (
                    <Stack gap={6} pr="md" pb={10} pl={list.length > 1 ? 52 : 36}>
                      {area.perms.map((perm) => (
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
                          <Text size="sm">{permLabel(perm)}</Text>
                        </label>
                      ))}
                    </Stack>
                  )}
                </Fragment>
              )
            })}
          </Fragment>
        ))}
      </Paper>
    </Stack>
  )
}
