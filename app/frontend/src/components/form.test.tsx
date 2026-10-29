import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { Select, TextInput } from '@mantine/core'
import { renderWithProviders } from '@/test/render'
import { Field } from './form'

describe('Field', () => {
  it('ties its label to the control inside it', () => {
    renderWithProviders(
      <Field label="Name der Gruppe">
        <TextInput placeholder="z. B. Keramik" />
      </Field>,
    )
    expect(screen.getByLabelText('Name der Gruppe')).toHaveAttribute('placeholder', 'z. B. Keramik')
  })

  it('keeps an id the control already has', () => {
    renderWithProviders(
      <Field label="Leitung">
        <Select id="lead" data={['Anna']} />
      </Field>,
    )
    expect(screen.getByLabelText('Leitung')).toHaveAttribute('id', 'lead')
  })
})
