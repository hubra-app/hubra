/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_TENANT_APP_URL?: string
  readonly VITE_SSO_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
