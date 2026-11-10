import type { EventCreate, EventTemplateData } from '@/api/events'

/** The template's fields the event form has no field for, to send along
 * when the event is created (the end date keeps the template's length). */
export function templateExtras(data: EventTemplateData | null, date: string): Partial<EventCreate> {
  if (!data) return {}
  const extras: Partial<EventCreate> = {}
  if (data.meeting_url) extras.meetingUrl = data.meeting_url
  if (data.all_day) extras.allDay = true
  if (data.category) extras.category = data.category
  if (data.cover_image_url) extras.coverImageUrl = data.cover_image_url
  if (data.color) extras.color = data.color
  if (data.days && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
    const end = new Date(`${date}T00:00:00Z`)
    end.setUTCDate(end.getUTCDate() + data.days)
    extras.endDate = end.toISOString().slice(0, 10)
  }
  return extras
}
