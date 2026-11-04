export function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

/** The ## headings of an article, for its contents list. */
export function headingsOf(source: string): { id: string; text: string }[] {
  return source
    .split('\n')
    .filter((l) => l.startsWith('## '))
    .map((l) => {
      const text = l.slice(3).trim()
      return { id: slugify(text), text }
    })
}
