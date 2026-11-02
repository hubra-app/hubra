import { useState, type ReactNode } from 'react'
import { tr } from '@/lang'
import { ConfirmModal } from './ui'

interface ConfirmRequest {
  title: string
  body?: string
  confirmLabel?: string
  run: () => void
}

/**
 * Asks before a destructive action: `confirm({ title, body, run })` opens
 * the shared ConfirmModal, `dialog` is rendered once by the screen.
 */
export function useConfirm(): [(req: ConfirmRequest) => void, ReactNode] {
  const [req, setReq] = useState<ConfirmRequest | null>(null)
  const dialog = (
    <ConfirmModal
      open={req !== null}
      title={req?.title ?? ''}
      body={req?.body}
      confirmLabel={req?.confirmLabel ?? tr('Löschen', 'Delete')}
      onConfirm={() => req?.run()}
      onClose={() => setReq(null)}
    />
  )
  return [setReq, dialog]
}
