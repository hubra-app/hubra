import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button, TextInput } from '@mantine/core'
import { renderWithProviders } from '@/test/render'
import { Modal } from './feedback'

function Dialog({ onSubmit }: { onSubmit: () => void }) {
  return (
    <Modal
      open
      onClose={() => {}}
      title="Gruppe"
      onSubmit={(e) => {
        e?.preventDefault()
        onSubmit()
      }}
      footer={
        <>
          <Button variant="default">Abbrechen</Button>
          <Button type="submit">Speichern</Button>
        </>
      }
    >
      <TextInput label="Name" />
    </Modal>
  )
}

describe('Modal with onSubmit', () => {
  it('submits when Enter is pressed in a field', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(<Dialog onSubmit={onSubmit} />)
    await user.type(screen.getByLabelText('Name'), 'Vorstand{Enter}')
    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('submits from the save button, not from the other buttons', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(<Dialog onSubmit={onSubmit} />)
    await user.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(onSubmit).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(onSubmit).toHaveBeenCalledOnce()
  })
})
