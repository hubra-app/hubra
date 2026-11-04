import { Fragment, type ReactNode } from 'react'
import { Code } from '@mantine/core'
import { Link } from 'react-router-dom'
import { slugify } from '@/lib/markdown'

/**
 * A small Markdown subset for the help articles, which we write ourselves:
 * ## and ### headings, paragraphs, - and 1. lists, > notes, ``` code blocks,
 * | tables |, and inline **bold**, `code` and [links](/path or https://…).
 * No HTML is ever passed through.
 */

function safeHref(href: string): string | null {
  if (href.startsWith('/') || href.startsWith('#')) return href
  try {
    const url = new URL(href)
    return url.protocol === 'https:' || url.protocol === 'http:' || url.protocol === 'mailto:' ? href : null
  } catch {
    return null
  }
}

export function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g).filter(Boolean)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
        if (part.startsWith('`') && part.endsWith('`'))
          return (
            <Code key={i} fz="0.88em">
              {part.slice(1, -1)}
            </Code>
          )
        const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part)
        if (link) {
          const href = safeHref(link[2])
          if (!href) return <Fragment key={i}>{link[1]}</Fragment>
          return href.startsWith('/') ? (
            <Link key={i} to={href}>
              {link[1]}
            </Link>
          ) : (
            <a key={i} href={href} rel="noopener noreferrer">
              {link[1]}
            </a>
          )
        }
        return <Fragment key={i}>{part}</Fragment>
      })}
    </>
  )
}

export function Markdown({ source }: { source: string }) {
  const lines = source.replace(/\r/g, '').split('\n')
  const out: ReactNode[] = []
  let i = 0
  let key = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }
    if (line.startsWith('```')) {
      const body: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) body.push(lines[i++])
      i++
      out.push(
        <pre key={key++}>
          <code>{body.join('\n')}</code>
        </pre>,
      )
      continue
    }
    if (line.startsWith('### ')) {
      const text = line.slice(4).trim()
      out.push(
        <h3 key={key++} id={slugify(text)}>
          <Inline text={text} />
        </h3>,
      )
      i++
      continue
    }
    if (line.startsWith('## ')) {
      const text = line.slice(3).trim()
      out.push(
        <h2 key={key++} id={slugify(text)}>
          <Inline text={text} />
        </h2>,
      )
      i++
      continue
    }
    if (line.startsWith('> ')) {
      const body: string[] = []
      while (i < lines.length && lines[i].startsWith('> ')) body.push(lines[i++].slice(2))
      out.push(
        <blockquote key={key++}>
          <p>
            <Inline text={body.join(' ')} />
          </p>
        </blockquote>,
      )
      continue
    }
    if (line.startsWith('|')) {
      const rows: string[][] = []
      while (i < lines.length && lines[i].startsWith('|')) {
        const cells = lines[i]
          .trim()
          .replace(/^\||\|$/g, '')
          .split('|')
          .map((c) => c.trim())
        if (!cells.every((c) => /^:?-+:?$/.test(c))) rows.push(cells)
        i++
      }
      const [head, ...body] = rows
      out.push(
        <table key={key++}>
          <thead>
            <tr>
              {head.map((c, j) => (
                <th key={j}>
                  <Inline text={c} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((r, k) => (
              <tr key={k}>
                {r.map((c, j) => (
                  <td key={j}>
                    <Inline text={c} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>,
      )
      continue
    }
    const ordered = /^\d+\.\s/.test(line)
    if (ordered || line.startsWith('- ')) {
      const items: string[] = []
      const re = ordered ? /^\d+\.\s+/ : /^-\s+/
      while (i < lines.length && re.test(lines[i])) {
        let item = lines[i++].replace(re, '')
        // An indented next line goes on with the same item.
        while (i < lines.length && /^\s{2,}\S/.test(lines[i])) item += ' ' + lines[i++].trim()
        items.push(item)
      }
      const List = ordered ? 'ol' : 'ul'
      out.push(
        <List key={key++}>
          {items.map((t, j) => (
            <li key={j}>
              <Inline text={t} />
            </li>
          ))}
        </List>,
      )
      continue
    }
    const para: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{2,3} |> |```|\||- |\d+\.\s)/.test(lines[i])
    )
      para.push(lines[i++].trim())
    out.push(
      <p key={key++}>
        <Inline text={para.join(' ')} />
      </p>,
    )
  }
  return <div className="sp-prose">{out}</div>
}
