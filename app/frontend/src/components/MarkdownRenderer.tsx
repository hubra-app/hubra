import { useState, type ImgHTMLAttributes } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useT } from '@/locales/i18n'
import { foreignImageHost } from '@/components/foreignImage'


function PostImage({ src, alt, title }: Pick<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'alt' | 'title'>) {
  const { t } = useT()
  const [shown, setShown] = useState(false)
  const host = foreignImageHost(typeof src === 'string' ? src : undefined)
  const img = <img src={src} alt={alt} title={title} referrerPolicy="no-referrer" style={{ maxWidth: '100%', height: 'auto' }} />
  if (!host || shown) return img
  return (
    <button
      type="button"
      onClick={() => setShown(true)}
      style={{
        display: 'inline-block',
        border: '1px dashed var(--hb-border)',
        borderRadius: '6px',
        padding: '6px 10px',
        background: 'transparent',
        color: 'var(--mantine-color-anchor)',
        cursor: 'pointer',
        font: 'inherit',
      }}
    >
      {alt ? `${alt}: ` : ''}
      {t('common.externalImage', 'Bild von {{host}} anzeigen', { host })}
    </button>
  )
}

interface MarkdownRendererProps {
  content: string
  className?: string
}

export function MarkdownRenderer({
  content,
  className,
}: MarkdownRendererProps) {
  return (
    <div className={className}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: (props) => (
            <h2
              style={{
                fontSize: 'var(--mantine-font-size-lg)',
                fontWeight: 700,
                color: 'var(--mantine-color-ink-8)',
                marginTop: '1em',
                marginBottom: '0.5em',
              }}
              {...props}
            />
          ),
          h3: (props) => (
            <h3
              style={{
                fontSize: 'var(--mantine-font-size-md)',
                fontWeight: 700,
                color: 'var(--mantine-color-ink-8)',
                marginTop: '0.8em',
                marginBottom: '0.4em',
              }}
              {...props}
            />
          ),
          h4: (props) => (
            <h4
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 600,
                color: 'var(--mantine-color-ink-8)',
                marginTop: '0.6em',
                marginBottom: '0.3em',
              }}
              {...props}
            />
          ),
          blockquote: (props) => (
            <blockquote
              style={{
                borderLeft: '3px solid var(--mantine-color-acc-6)',
                paddingLeft: '12px',
                marginLeft: 0,
                marginBottom: '0.5em',
                color: 'var(--mantine-color-ink-4)',
                fontStyle: 'italic',
              }}
              {...props}
            />
          ),
          code: (props) => (
            <code
              style={{
                background: 'var(--mantine-color-surface-1)',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: 'var(--mantine-font-size-xs)',
                fontFamily: 'var(--mantine-font-family-monospace)',
              }}
              {...props}
            />
          ),
          pre: (props) => (
            <pre
              style={{
                background: 'var(--mantine-color-surface-1)',
                borderRadius: '8px',
                padding: '12px',
                overflowX: 'auto',
                marginBottom: '0.5em',
              }}
              {...props}
            />
          ),
          ul: (props) => (
            <ul
              style={{
                paddingLeft: '20px',
                marginBottom: '0.5em',
                listStyleType: 'disc',
              }}
              {...props}
            />
          ),
          ol: (props) => (
            <ol
              style={{
                paddingLeft: '20px',
                marginBottom: '0.5em',
                listStyleType: 'decimal',
              }}
              {...props}
            />
          ),
          hr: (props) => (
            <hr
              style={{
                border: 'none',
                borderTop: '1px solid var(--hb-border)',
                margin: '1em 0',
              }}
              {...props}
            />
          ),
          img: ({ src, alt, title }) => <PostImage src={src} alt={alt} title={title} />,
          a: (props) => (
            <a
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: 'var(--mantine-color-anchor)',
                textDecoration: 'underline',
              }}
              {...props}
            />
          ),
        }}
      >
        {content}
      </Markdown>
    </div>
  )
}
