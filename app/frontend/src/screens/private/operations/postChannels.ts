/** The channels a post goes to, as the form keeps them: null for every
 * channel (also ones the club adds later), else only those listed. */
export type ChannelPick = string[] | null

/** Whether *key* is on in *pick*. */
export function isOn(pick: ChannelPick, key: string): boolean {
  return pick === null || pick.includes(key)
}

/** *pick* with *key* switched; every channel on is stored as null. */
export function toggle(pick: ChannelPick, key: string, all: string[]): ChannelPick {
  const now = pick ?? all
  const next = now.includes(key) ? now.filter((k) => k !== key) : [...now, key]
  if (all.every((k) => next.includes(k))) return null
  return all.filter((k) => next.includes(k))
}
