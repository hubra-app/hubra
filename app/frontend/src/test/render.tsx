import type { ReactElement, ReactNode } from 'react'
import { render } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cssVariablesResolver, theme } from '@hubra/ui'
import '@/locales/i18n'

/** Renders `ui` inside the providers the app puts around every screen. */
export function renderWithProviders(ui: ReactElement, { route = '/' } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    // env="test": no transitions or portals, as Mantine recommends for tests.
    <MantineProvider theme={theme} cssVariablesResolver={cssVariablesResolver} env="test">
      <MemoryRouter initialEntries={[route]}>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </MemoryRouter>
    </MantineProvider>
  )
  return render(ui, { wrapper: Wrapper })
}
