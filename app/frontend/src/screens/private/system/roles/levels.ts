import type { PermissionEntry } from '@/api/system'

/**
 * A role's access to one area, in four steps instead of a dozen ticks.
 * Each step holds the one before it: seeing, then also creating and
 * changing, then also deleting and the rights that reach further
 * (exporting members, giving roles, moderating).
 */
export type Level = 'none' | 'view' | 'edit' | 'all'
export const LEVELS: Level[] = ['none', 'view', 'edit', 'all']

/** Seeing, and taking part as a member: signing up, voting, commenting. */
const VIEW_ACTIONS = new Set([
  'read',
  'read_reminders',
  'calculate_cost',
  'register',
  'vote',
  'comment',
  'like',
  'checkin',
  'checkout',
  'instruct_self',
])
/** Only in "Alles": they delete, or reach past the area itself. */
const ALL_ONLY_ACTIONS = new Set([
  'delete',
  'moderate',
  'manage',
  'export',
  'set_permissions',
  'update.is_admin',
  'update.role_ids',
])

export function actionLevel(action: string): Exclude<Level, 'none'> {
  if (VIEW_ACTIONS.has(action)) return 'view'
  if (ALL_ONLY_ACTIONS.has(action)) return 'all'
  return 'edit'
}

/** The keys one level gives in an area. */
export function levelKeys(perms: PermissionEntry[], level: Level): string[] {
  const rank = LEVELS.indexOf(level)
  return perms.filter((p) => LEVELS.indexOf(actionLevel(p.action)) <= rank).map((p) => p.key)
}

/**
 * The levels worth offering in an area: one that gives the same keys as
 * the step before it is left out (an area that can only be read has no
 * "Bearbeiten").
 */
export function offeredLevels(perms: PermissionEntry[]): Level[] {
  const out: Level[] = ['none']
  let prev = 0
  for (const level of LEVELS.slice(1)) {
    const count = levelKeys(perms, level).length
    if (count > prev) out.push(level)
    prev = count
  }
  return out
}

/** The level a role's keys match exactly, or null for a custom mix. */
export function currentLevel(
  perms: PermissionEntry[],
  held: Set<string> | undefined,
): Level | null {
  const has = perms.filter((p) => held?.has(p.key)).map((p) => p.key)
  for (const level of offeredLevels(perms)) {
    const keys = levelKeys(perms, level)
    if (keys.length === has.length && keys.every((k) => held?.has(k))) return level
  }
  return null
}

export interface Area {
  /** `blueprint:resource` */
  key: string
  blueprint: string
  resource: string
  perms: PermissionEntry[]
}

/** The catalog cut into areas (one per resource), in a stable order. */
export function toAreas(allPerms: PermissionEntry[]): Area[] {
  const map = new Map<string, Area>()
  for (const p of allPerms) {
    const key = `${p.blueprint}:${p.resource}`
    let area = map.get(key)
    if (!area) {
      area = { key, blueprint: p.blueprint, resource: p.resource, perms: [] }
      map.set(key, area)
    }
    if (!area.perms.some((q) => q.key === p.key)) area.perms.push(p)
  }
  return [...map.values()].sort((a, b) => a.key.localeCompare(b.key))
}
