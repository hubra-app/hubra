import { apiFetch } from '@hubra/api-client'

/** A person holding one of the member club's functions, when it shares them. */
export interface ClubContact {
  function: string
  name: string
  email: string | null
}

/** A member club, or an invited one, as the association sees it. */
export interface MemberClub {
  id: number
  slug: string
  name: string
  status: 'invited' | 'active'
  shareContacts: boolean
  invitedAt: string
  acceptedAt: string | null
  /** Active members; null until the club accepts. */
  members: number | null
  contacts: ClubContact[]
}

/** An association the club belongs to or is invited by. */
export interface Association {
  id: number
  slug: string
  name: string
  status: 'invited' | 'active'
  shareContacts: boolean
  invitedAt: string
  acceptedAt: string | null
}

/** An event an association shares with its member clubs. */
export interface AssociationEvent {
  id: number
  title: string
  date: string
  endDate: string | null
  time: string | null
  allDay: boolean
  location: string | null
  description: string | null
  onlineUrl: string | null
  type: string
  federation: string
  federationSlug: string
}

export function listMemberClubs(): Promise<{ clubs: MemberClub[] }> {
  return apiFetch('/app/federation/clubs')
}

export function inviteMemberClub(slug: string): Promise<MemberClub> {
  return apiFetch('/app/federation/clubs', { method: 'POST', body: JSON.stringify({ slug }) })
}

export async function removeMemberClub(id: number): Promise<void> {
  await apiFetch(`/app/federation/clubs/${id}`, { method: 'DELETE' })
}

export function listAssociations(): Promise<{ associations: Association[] }> {
  return apiFetch('/app/settings/associations')
}

export function acceptAssociation(id: number, shareContacts: boolean): Promise<Association> {
  return apiFetch(`/app/settings/associations/${id}/accept`, {
    method: 'POST',
    body: JSON.stringify({ shareContacts }),
  })
}

export function setAssociationContacts(id: number, shareContacts: boolean): Promise<Association> {
  return apiFetch(`/app/settings/associations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ shareContacts }),
  })
}

export async function leaveAssociation(id: number): Promise<void> {
  await apiFetch(`/app/settings/associations/${id}`, { method: 'DELETE' })
}

export function listAssociationEvents(): Promise<{ events: AssociationEvent[] }> {
  return apiFetch('/app/events/from-associations')
}
