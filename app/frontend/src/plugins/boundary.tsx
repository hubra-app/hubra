import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Alert } from '@mantine/core'
import i18n from '@/locales/i18n'

interface Props {
  /** The plugin's id, for the log. */
  plugin: string
  /** Show a notice in place of what failed (screens and tabs); slots just drop out. */
  notice?: boolean
  children: ReactNode
}

/**
 * Keeps a plugin that throws from taking the screen around it down: what
 * the plugin rendered disappears (or shows a short notice) and the rest of
 * the page keeps working.
 */
export class PluginBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[plugin ${this.props.plugin}]`, error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    if (!this.props.notice) return null
    return (
      <Alert color="red" variant="light" my="md">
        {i18n.t('modules.pluginFailed', 'Diese Erweiterung konnte nicht angezeigt werden.')}
      </Alert>
    )
  }
}
