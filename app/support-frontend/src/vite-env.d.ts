/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_SSO_URL?: string
  readonly VITE_COS_URL?: string
  readonly VITE_MANAGE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
