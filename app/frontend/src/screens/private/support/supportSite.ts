/** Help, roadmap, status and reports (app/support-frontend). */
export const SUPPORT_URL: string = import.meta.env.VITE_SUPPORT_URL ?? 'https://support.hubra.club'

/** The support site's report form with this page's address filled in. For
 * screens outside the shell (404, crash), where the in-app dialog is not
 * mounted. */
export function reportProblemUrl(page: string = window.location.href): string {
  return `${SUPPORT_URL}/melden?page=${encodeURIComponent(page)}`
}
