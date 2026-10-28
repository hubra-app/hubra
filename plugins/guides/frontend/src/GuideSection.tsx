import { useState } from 'react'
import { Button, Textarea, TextInput } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { MarkdownRenderer, useAuth, useT, useToast } from '@hubra/plugin-sdk'
import { getGuide, saveGuide } from './api'

/** Shown in an inventory item's detail panel. */
export function GuideSection({ itemId }: { itemId: number }) {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = hasPermission('guides.guides.write')
  const { data: guide } = useQuery({
    queryKey: ['guides', itemId],
    queryFn: () => getGuide(itemId),
  })
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)

  const startEdit = () => {
    setText(guide?.guide ?? '')
    setUrl(guide?.guideUrl ?? '')
    setEditing(true)
  }

  const save = async () => {
    setBusy(true)
    try {
      await saveGuide(itemId, { guide: text || null, guideUrl: url || null })
      await queryClient.invalidateQueries({ queryKey: ['guides', itemId] })
      setEditing(false)
      notify('success', t('inventory.guide.saved', 'Guide saved'))
    } catch (err: unknown) {
      notify(
        'error',
        t('inventory.failed', 'Fehler'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    } finally {
      setBusy(false)
    }
  }

  const empty = !guide?.guide && !guide?.guideUrl
  if (!guide || (empty && !canWrite && !editing)) return null

  return (
    <div style={{ padding: '16px 20px', borderTop: '1px solid #e3eae6' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <strong style={{ fontSize: 'var(--mantine-font-size-sm)' }}>
          {t('inventory.guide.title', 'Guide')}
        </strong>
        {canWrite && !editing && (
          <Button size="xs" variant="subtle" onClick={startEdit}>
            {empty ? t('inventory.guide.add', 'Add guide') : t('common.edit', 'Edit')}
          </Button>
        )}
      </div>
      {editing ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Textarea
            value={text}
            onChange={(e) => setText(e.currentTarget.value)}
            autosize
            minRows={6}
            placeholder={t(
              'inventory.guide.placeholder',
              'Steps, safety rules, what to check after use. Markdown works.',
            )}
          />
          <TextInput
            value={url}
            onChange={(e) => setUrl(e.currentTarget.value)}
            label={t('inventory.guide.link', 'Link to manual or video')}
            placeholder="https://"
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button variant="subtle" onClick={() => setEditing(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="default" onClick={save} loading={busy}>
              {t('common.save')}
            </Button>
          </div>
        </div>
      ) : (
        <>
          {guide.guide && <MarkdownRenderer content={guide.guide} />}
          {guide.guideUrl && (
            <a href={guide.guideUrl} target="_blank" rel="noopener noreferrer">
              {t('inventory.guide.openLink', 'Open manual')}
            </a>
          )}
        </>
      )}
    </div>
  )
}
