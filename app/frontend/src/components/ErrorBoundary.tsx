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
                Something went wrong
              </Text>
              <Text size="sm" c="dimmed" lh={1.6}>
                An unexpected error occurred. Please refresh the page to try
                again.
              </Text>
              <Code block>{this.state.error?.message}</Code>
              <Button onClick={() => window.location.reload()}>
                Reload page
              </Button>
            </Stack>
          </Paper>
        </Center>
      )
    }

    return this.props.children
  }
}
