/**
 * Translation coverage: which texts a language lacks, per source (Hubra
 * itself or a plugin). Every key some language has counts as wanted in all
 * of them; a key a plugin ships belongs to that plugin.
 */

/** Nested translation.json → dotted key → text (empty texts left out). */
export function flatten(node: unknown, prefix = '', out: Record<string, string> = {}) {
  if (typeof node === 'string') {
    if (node.trim()) out[prefix] = node
  } else if (node && typeof node === 'object') {
    for (const [k, v] of Object.entries(node)) flatten(v, prefix ? `${prefix}.${k}` : k, out)
  }
  return out
}

export interface CoverageSource {
  /** `core`, or the plugin's id. */
  id: string
  /** Keys this source ships, in any language. */
  keys: Set<string>
}

export interface CoverageRow {
  id: string
  total: number
  /** Missing keys per locale, sorted. */
  missing: Record<string, string[]>
}

/**
 * *texts*: what the app has per locale now (built in, plugins and the
 * platform's own texts). *plugins*: each plugin's keys. Rows: Hubra first,
 * then the plugins by id; a source without keys is left out.
 */
export function coverage(
  texts: Record<string, Record<string, string>>,
  plugins: CoverageSource[],
): CoverageRow[] {
  const locales = Object.keys(texts)
  const all = new Set<string>()
  for (const loc of locales) for (const k of Object.keys(texts[loc])) all.add(k)
  const owner = new Map<string, string>()
  for (const p of plugins) for (const k of p.keys) owner.set(k, p.id)
  const bySource = new Map<string, string[]>()
  for (const k of all) {
    const id = owner.get(k) ?? 'core'
    const list = bySource.get(id) ?? []
    list.push(k)
    bySource.set(id, list)
  }
  const ids = ['core', ...plugins.map((p) => p.id).sort()].filter(
    (id, i, arr) => arr.indexOf(id) === i && bySource.has(id),
  )
  return ids.map((id) => {
    const keys = bySource.get(id) ?? []
    const missing: Record<string, string[]> = {}
    for (const loc of locales) missing[loc] = keys.filter((k) => !texts[loc][k]).sort()
    return { id, total: keys.length, missing }
  })
}

/** Share of *row*'s texts that *locale* has, 0 to 100, rounded down. */
export function percent(row: CoverageRow, locale: string): number {
  if (!row.total) return 100
  return Math.floor(((row.total - (row.missing[locale]?.length ?? 0)) * 100) / row.total)
}
