/** `members_bp` → `Members`. */
export function blueprintLabel(bp: string): string {
  const stripped = bp.replace(/_bp$/, '')
  return stripped.charAt(0).toUpperCase() + stripped.slice(1)
}
