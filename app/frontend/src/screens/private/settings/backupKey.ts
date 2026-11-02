// Club backup key helpers: they run only in the browser, so the private
// key never leaves it.
import { identityToRecipient } from 'age-encryption'

export const PUBLIC_RE = /^age1[02-9ac-hj-np-z]{58}$/
const PRIVATE_RE = /^AGE-SECRET-KEY-1[02-9AC-HJ-NP-Z]{58}$/

/** The private keys in a pasted or uploaded key file (comments are fine). */
export function privateKeysIn(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))
    .filter((line) => PRIVATE_RE.test(line.toUpperCase()))
    .map((line) => line.toUpperCase())
}

/** Whether `text` holds the private key that belongs to `publicKey`. */
export async function keyFileMatches(text: string, publicKey: string): Promise<boolean> {
  for (const key of privateKeysIn(text)) {
    try {
      if ((await identityToRecipient(key)) === publicKey) return true
    } catch {
      // not a key age can read: try the next line
    }
  }
  return false
}

/** The same layout `age-keygen` writes, so the age tool reads it as is. */
export function keyFile(privateKey: string, publicKey: string, club: string, now = new Date()) {
  return [
    `# Hubra backup key for ${club}`,
    `# created: ${now.toISOString().replace(/\.\d+Z$/, 'Z')}`,
    `# public key: ${publicKey}`,
    privateKey,
    '',
  ].join('\n')
}
