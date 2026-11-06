import { categoryColors } from '@hubra/ui'

/** Help, roadmap, status and reports (app/support-frontend). */
export const SUPPORT_URL: string = import.meta.env.VITE_SUPPORT_URL ?? 'https://support.hubra.club'

/** The support site's bug report form, with the page it is about filled in. */
export function reportProblemUrl(page: string): string {
  return `${SUPPORT_URL}/melden?where=${encodeURIComponent(page)}`
}
export const EVENT_TYPE_COLORS: Record<string, string> = {
  Workshop: categoryColors.blue,
  Social: categoryColors.green,
  Certification: categoryColors.pink,
  Meeting: categoryColors.slate,
};
