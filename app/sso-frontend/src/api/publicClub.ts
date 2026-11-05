import { apiFetch } from '@hubra/api-client'

export interface PublicClubEvent {
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
  category: string | null
  coverImageUrl: string | null
}

/** What a club shows anyone on its public page (off until the club turns it on). */
export interface PublicClub {
  slug: string
  name: string
  description: string | null
  website: string | null
  logoVersion: string | null
  acceptsRequests: boolean
  /** Trial trainings can be booked on /clubs/<slug>/trial. */
  trials: boolean
  events: PublicClubEvent[]
  /** The public events as a calendar feed (.ics), or null. */
  calendar: string | null
  groups: { name: string; description: string | null; sessions: string | null; color: string | null }[]
}

/** The club's public page; rejects with a 404 when the club has none. */
export function getPublicClub(slug: string): Promise<PublicClub> {
  return apiFetch(`/global/clubs/${encodeURIComponent(slug)}/public`)
}
