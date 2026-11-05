import { apiFetch } from '@hubra/api-client'

/** A training that takes trial bookings, as the club's trial page lists it. */
export interface TrialEvent {
  id: number
  title: string
  date: string
  time: string | null
  location: string | null
  description: string | null
  category: string
  /** Trial places still free. */
  free: number
}

export interface TrialPage {
  club: { name: string; slug: string }
  events: TrialEvent[]
}

export interface TrialBooking {
  status: 'pending' | 'confirmed' | 'attended' | 'no_show' | 'cancelled' | 'invited'
  firstName: string
  event: TrialEvent
}

export interface TrialInput {
  eventId: number
  firstName: string
  lastName: string
  email: string
  phone?: string
  birthDate?: string
  message?: string
  consent: boolean
  lang: string
  /** Stays empty; bots fill it. */
  website?: string
}

const base = (slug: string) => `/app/events/public/${encodeURIComponent(slug)}/trials`

export function getTrialPage(slug: string): Promise<TrialPage> {
  return apiFetch(base(slug))
}

export function bookTrial(slug: string, input: TrialInput): Promise<{ status: 'pending' }> {
  return apiFetch(base(slug), { method: 'POST', body: JSON.stringify(input) })
}

export function confirmTrial(slug: string, token: string): Promise<TrialBooking> {
  return apiFetch(`${base(slug)}/confirm`, { method: 'POST', body: JSON.stringify({ token }) })
}

export function cancelTrial(slug: string, token: string): Promise<TrialBooking> {
  return apiFetch(`${base(slug)}/cancel`, { method: 'POST', body: JSON.stringify({ token }) })
}
