import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  listRoles,
  createRole,
  updateRole,
  deleteRole,
  getRolePermissions,
  setRolePermissions,
  type Role,
} from '@/api/settings'
import { getSystemPermissions, type PermissionEntry } from '@/api/system'
import { qk } from '@/data/keys'
import type { RoleTemplate } from '@/data/roleTemplates'

export interface RolesData {
  roles: Role[]
  allPerms: PermissionEntry[]
  rolePerms: Record<string, Set<string>>
}

export interface RoleInput {
  name: string
  description: string | null
  isAdmin: boolean
}

/**
 * The club's roles with their permissions, and the changes made to them.
 * A permission ticked in the table shows at once and goes back if the
 * server refuses it.
 */
export function useRoles() {
  const queryClient = useQueryClient()
  const [localPerms, setLocalPerms] = useState<Record<string, Set<string>>>({})

  const { data, isLoading } = useQuery({
    queryKey: qk.settings.rolesPermissions,
    queryFn: async (): Promise<RolesData> => {
      const [roleList, perms] = await Promise.all([listRoles(), getSystemPermissions()])
      const permsMap: Record<string, Set<string>> = {}
      for (const role of roleList) {
        permsMap[role.id] = new Set(await getRolePermissions(role.id))
      }
      return { roles: roleList, allPerms: perms, rolePerms: permsMap }
    },
    staleTime: Infinity,
  })
  const roles = useMemo(() => data?.roles ?? [], [data?.roles])
  const allPerms = useMemo(() => data?.allPerms ?? [], [data?.allPerms])
  const rolePerms = useMemo(() => {
    const merged: Record<string, Set<string>> = { ...(data?.rolePerms ?? {}) }
    for (const [roleId, set] of Object.entries(localPerms)) merged[roleId] = set
    return merged
  }, [data?.rolePerms, localPerms])

  const update = (fn: (old: RolesData) => RolesData) =>
    queryClient.setQueryData<RolesData>(qk.settings.rolesPermissions, (old) =>
      old ? fn(old) : old,
    )
  const roleListChanged = () => queryClient.invalidateQueries({ queryKey: qk.lookups })

  /** Saves a role's new permissions; on failure it shows the old ones again. */
  const savePerms = (role: Role, next: Set<string>) => {
    const base = rolePerms[role.id] ?? new Set<string>()
    setLocalPerms((prev) => ({ ...prev, [role.id]: next }))
    return setRolePermissions(role.id, Array.from(next)).catch((err: unknown) => {
      setLocalPerms((prev) => ({ ...prev, [role.id]: base }))
      throw err
    })
  }

  const togglePerm = (role: Role, key: string) => {
    const next = new Set(rolePerms[role.id] ?? [])
    if (next.has(key)) next.delete(key)
    else next.add(key)
    return savePerms(role, next)
  }

  const setPerms = (role: Role, keys: string[], on: boolean) => {
    const next = new Set(rolePerms[role.id] ?? [])
    for (const key of keys) {
      if (on) next.add(key)
      else next.delete(key)
    }
    return savePerms(role, next)
  }

  /** Gives the role exactly `keys` of an area's permissions. */
  const setAreaPerms = (role: Role, area: string[], keys: string[]) => {
    const next = new Set(rolePerms[role.id] ?? [])
    for (const key of area) next.delete(key)
    for (const key of keys) next.add(key)
    return savePerms(role, next)
  }

  const create = async ({ name, description, isAdmin }: RoleInput) => {
    let role = await createRole(name, description)
    if (isAdmin) role = await updateRole(role.id, { name, description, is_admin: true })
    update((old) => ({
      ...old,
      roles: [...old.roles, role],
      rolePerms: { ...old.rolePerms, [role.id]: new Set() },
    }))
    roleListChanged()
    return role
  }

  const save = async (role: Role, { name, description, isAdmin }: RoleInput) => {
    const updated = await updateRole(role.id, { name, description, is_admin: isAdmin })
    update((old) => ({ ...old, roles: old.roles.map((r) => (r.id === updated.id ? updated : r)) }))
    roleListChanged()
    return updated
  }

  const remove = async (role: Role) => {
    await deleteRole(role.id)
    update((old) => {
      const rolePerms = { ...old.rolePerms }
      delete rolePerms[role.id]
      return { ...old, roles: old.roles.filter((r) => r.id !== role.id), rolePerms }
    })
    setLocalPerms((prev) => {
      const next = { ...prev }
      delete next[role.id]
      return next
    })
    roleListChanged()
  }

  /** Creates the template's missing roles and sets the permissions of all of them. */
  const applyTemplate = async (template: RoleTemplate) => {
    for (const tr of template.roles) {
      const existing = roles.find((r) => r.name === tr.name)
      let roleId: string
      if (existing) {
        roleId = existing.id
        // An existing role keeps its admin flag: the system roles' flag is
        // locked, and taking admin from a role the club uses is no template's job.
        if (tr.description && existing.description !== tr.description) {
          await updateRole(roleId, { name: existing.name, description: tr.description })
        }
        if (existing.isAdmin) continue
      } else {
        roleId = (await createRole(tr.name, tr.description)).id
        if (tr.is_admin) {
          await updateRole(roleId, { name: tr.name, description: tr.description, is_admin: true })
        }
      }
      if (!tr.is_admin && tr.permissions.length > 0) {
        await setRolePermissions(roleId, tr.permissions)
      }
    }
    await queryClient.invalidateQueries({ queryKey: qk.settings.rolesPermissions })
    roleListChanged()
  }

  return {
    roles,
    allPerms,
    rolePerms,
    isLoading,
    togglePerm,
    setPerms,
    setAreaPerms,
    create,
    save,
    remove,
    applyTemplate,
  }
}
