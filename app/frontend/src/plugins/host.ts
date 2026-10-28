/**
 * Puts the app's libraries and `@hubra/plugin-sdk` on `window.HubraPluginHost`,
 * where plugin bundles find them (see scripts/build-plugin.mjs).  Loaded
 * only once a club has a plugin with a frontend, so the extra weight of
 * whole libraries is only paid then.
 */
import * as React from 'react'
import * as ReactDOM from 'react-dom'
import * as jsxRuntime from 'react/jsx-runtime'
import * as routerDom from 'react-router-dom'
import * as mantineCore from '@mantine/core'
import * as mantineHooks from '@mantine/hooks'
import * as mantineNotifications from '@mantine/notifications'
import * as reactQuery from '@tanstack/react-query'
import * as reactI18next from 'react-i18next'
import * as sdk from './sdk'

/** The host API version; plugins built for a newer major refuse to load. */
export const HOST_API = 1

const host = {
  api: HOST_API,
  libs: {
    react: React,
    reactDom: ReactDOM,
    jsxRuntime,
    routerDom,
    mantineCore,
    mantineHooks,
    mantineNotifications,
    reactQuery,
    reactI18next,
  },
  sdk,
}

declare global {
  interface Window {
    HubraPluginHost?: typeof host
  }
}

window.HubraPluginHost = host
