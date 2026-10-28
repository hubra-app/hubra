export {
  BASE,
  SSO_URL,
  getInstance,
  getCookie,
  hasTokens,
  getRememberedEmail,
  clearTokens,
  setAuthFailureHandler,
  resetAuthFailure,
  setTenantSlug,
  apiFetch,
  apiFetchRaw,
} from "./client";
export type { InstanceInfo } from "./client";
