// Date, date-time and time fields that look the same in every browser and
// show dd.mm.yyyy and 24-hour times (the browser's own pickers follow the
// browser's language: 11/11/2026 and 2:00 PM on an English browser).
//
// They keep the values the old <input type="date|datetime-local|time">
// fields had, so a form changes only the component: "YYYY-MM-DD",
// "YYYY-MM-DDTHH:mm" and "HH:mm" strings, "" when empty.
import { DateInput, DateTimePicker, DatesProvider, TimePicker } from '@mantine/dates'
import type { DateInputProps, DateTimePickerProps, TimePickerProps } from '@mantine/dates'
import { IconCalendar, IconClock } from '@tabler/icons-react'
import 'dayjs/locale/de'
import type { ReactNode } from 'react'

const DATE_FORMAT = 'DD.MM.YYYY'

function locale(): string {
  const lang = typeof document !== 'undefined' ? document.documentElement.lang : ''
  return lang.startsWith('en') ? 'en' : 'de'
}

function Dates({ children }: { children: ReactNode }) {
  return <DatesProvider settings={{ locale: locale(), firstDayOfWeek: 1 }}>{children}</DatesProvider>
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "11.11.2026", "11.11.26", "1.2.2026" or "2026-11-01" as "YYYY-MM-DD";
 * null when it isn't a real date. */
export function parseDate(text: string): string | null {
  const t = text.trim()
  let y: number, m: number, d: number
  const ch = /^(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2}|\d{4})$/.exec(t)
  const iso = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(t)
  if (ch) {
    d = Number(ch[1])
    m = Number(ch[2])
    y = Number(ch[3])
    if (ch[3].length === 2) y += 2000
  } else if (iso) {
    y = Number(iso[1])
    m = Number(iso[2])
    d = Number(iso[3])
  } else {
    return null
  }
  const date = new Date(Date.UTC(y, m - 1, d))
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m - 1 || date.getUTCDate() !== d) return null
  return `${y}-${pad(m)}-${pad(d)}`
}

type DateFieldProps = Omit<DateInputProps, 'value' | 'onChange' | 'minDate' | 'maxDate'> & {
  value?: string | null
  onChange?: (value: string) => void
  /** Earliest and latest date, "YYYY-MM-DD" (like min/max of a date input). */
  min?: string
  max?: string
}

/** A date: typed as dd.mm.yyyy or picked from the calendar. */
export function DateField({ value, onChange, min, max, ...rest }: DateFieldProps) {
  return (
    <Dates>
      <DateInput
        valueFormat={DATE_FORMAT}
        dateParser={parseDate}
        placeholder="TT.MM.JJJJ"
        leftSection={<IconCalendar size={16} />}
        leftSectionPointerEvents="none"
        {...rest}
        value={value || null}
        onChange={(v) => onChange?.(v ?? '')}
        minDate={min || undefined}
        maxDate={max || undefined}
      />
    </Dates>
  )
}

type DateTimeFieldProps = Omit<DateTimePickerProps, 'value' | 'onChange' | 'minDate' | 'maxDate'> & {
  /** "YYYY-MM-DDTHH:mm", like a datetime-local input. */
  value?: string | null
  onChange?: (value: string) => void
  min?: string
  max?: string
}

const toMantine = (v: string | null | undefined) => (v ? `${v.replace('T', ' ').slice(0, 16)}:00` : null)
const fromMantine = (v: string | null) => (v ? v.replace(' ', 'T').slice(0, 16) : '')

/** A date with a time (deadlines, reminders). */
export function DateTimeField({ value, onChange, min, max, ...rest }: DateTimeFieldProps) {
  return (
    <Dates>
      <DateTimePicker
        valueFormat={`${DATE_FORMAT} HH:mm`}
        placeholder="TT.MM.JJJJ HH:MM"
        leftSection={<IconCalendar size={16} />}
        leftSectionPointerEvents="none"
        clearable
        {...rest}
        value={toMantine(value)}
        onChange={(v) => onChange?.(fromMantine(v))}
        minDate={min ? toMantine(min)! : undefined}
        maxDate={max ? toMantine(max)! : undefined}
      />
    </Dates>
  )
}

type TimeFieldProps = Omit<TimePickerProps, 'value' | 'onChange'> & {
  /** "HH:mm". */
  value?: string | null
  onChange?: (value: string) => void
}

/** A time of day, always 24 hours. */
export function TimeField({ value, onChange, ...rest }: TimeFieldProps) {
  return (
    <TimePicker
      format="24h"
      leftSection={<IconClock size={16} />}
      leftSectionPointerEvents="none"
      clearable
      {...rest}
      value={value ?? ''}
      onChange={(v) => onChange?.(v ? v.slice(0, 5) : '')}
    />
  )
}
