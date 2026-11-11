// An event's time is one text ("14:00–18:00"); the form edits it as von/bis.
const HM = String.raw`([01]?\d|2[0-3])[:.]([0-5]\d)`
const TIME_RANGE = new RegExp(String.raw`^\s*${HM}\s*(?:(?:[–—-]|bis)\s*${HM})?\s*(?:Uhr)?\s*$`)

/** "14:00–18:00" (or "9:30", "14.00 - 18.00 Uhr") as von/bis fields; any
 * other text is kept as it is. */
export function splitTime(time: string | null | undefined): {
  timeFrom: string
  timeTo: string
  timeText: string
} {
  const m = TIME_RANGE.exec(time ?? '')
  if (!m) return { timeFrom: '', timeTo: '', timeText: time ?? '' }
  const hm = (h: string, min: string) => `${h.padStart(2, '0')}:${min}`
  return { timeFrom: hm(m[1], m[2]), timeTo: m[3] ? hm(m[3], m[4]) : '', timeText: '' }
}

/** The event's time text from the von/bis fields. */
export function joinTime(v: { timeFrom: string; timeTo: string; timeText: string }): string {
  if (!v.timeFrom) return v.timeText
  return v.timeTo ? `${v.timeFrom}–${v.timeTo}` : v.timeFrom
}
