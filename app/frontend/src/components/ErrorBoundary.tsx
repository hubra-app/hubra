import i18n from 'i18next'
import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Paper, Text, Button, Stack, Center, Code } from '@mantine/core'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[ErrorBoundary] Uncaught error:', error, info.componentStack)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      return (
        <Center h="100vh" p="lg">
          <Paper shadow="lg" p="xl" maw={460}>
            <Stack gap="sm">
              <Text fz={18} fw={700} c="red">
                {i18n.t('app.errorTitle', 'Etwas ist schiefgelaufen')}
              </Text>
              <Text size="sm" c="dimmed" lh={1.6}>
                {i18n.t('app.errorReload', 'Ein unerwarteter Fehler ist aufgetreten. Bitte lade die Seite neu.')}
              </Text>
              <Code block>{this.state.error?.message}</Code>
              <Button onClick={() => window.location.reload()}>
                {i18n.t('app.reload', 'Seite neu laden')}
              </Button>
            </Stack>
          </Paper>
        </Center>
      )
    }

    return this.props.children
  }
}
