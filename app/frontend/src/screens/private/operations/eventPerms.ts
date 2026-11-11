import { useQuery } from '@tanstack/react-query'
import { useAuth, useData } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { listGroups } from '@/api/groups'
import type { ClubEvent } from '@/types'

/**
 * What the signed-in member may do with an event. Club-wide rights, a role
 * for the event's group, or having put the event up (the API checks the
 * same).
 */
export function useEventPerms() {
  const { currentUser, hasPermission } = useAuth()
  const { moduleList } = useData()
  const hosts = (ev: ClubEvent) =>
    currentUser != null && ev.createdById === Number(currentUser.id)
  const inScope = (key: string, ev: ClubEvent) => hasPermission(key, ev.groupId ?? undefined)
  const mayGroups = moduleList.some((m) => m.code === 'groups')
  const { data: groups = [] } = useQuery({
    queryKey: qk.groups.all,
    queryFn: listGroups,
    enabled: mayGroups,
  })
  return {
    canUpdate: (ev: ClubEvent) => inScope('events.events.update', ev) || hosts(ev),
    canDelete: (ev: ClubEvent) => inScope('events.events.delete', ev) || hosts(ev),
    canApprove: (ev: ClubEvent) => inScope('events.events.add_attendee', ev) || hosts(ev),
    // Club-wide, or a trainer holding the right for one group.
    canTakeRoll: (ev: ClubEvent) => inScope('events.events.add_attendee', ev),
    // Templates are club-wide: saving and listing them takes the club-wide right.
    canTemplates: hasPermission('events.events.create'),
    seesAttendance:
      hasPermission('events.events.add_attendee') ||
      groups.some((g) => hasPermission('events.events.add_attendee', g.id)),
    seesTrials: hasPermission('events.trials.read'),
  }
}
