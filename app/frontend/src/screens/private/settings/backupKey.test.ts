import { describe, expect, it } from 'vitest'
import { generateX25519Identity, identityToRecipient } from 'age-encryption'
import { keyFile, keyFileMatches, privateKeysIn } from './backupKey'

describe('club backup key helpers', () => {
  it('writes a key file the age tool reads and finds the key in it again', async () => {
    const priv = await generateX25519Identity()
    const pub = await identityToRecipient(priv)
    expect(pub).toMatch(/^age1[02-9ac-hj-np-z]{58}$/)

    const file = keyFile(priv, pub, 'fc-test', new Date('2026-11-02T10:00:00.123Z'))
    expect(file).toBe(
      `# Hubra backup key for fc-test\n# created: 2026-11-02T10:00:00Z\n# public key: ${pub}\n${priv}\n`,
    )
    expect(privateKeysIn(file)).toEqual([priv])
    expect(await keyFileMatches(file, pub)).toBe(true)
    // Pasted with stray spaces or in lower case still fits.
    expect(await keyFileMatches(`  ${priv.toLowerCase()}  `, pub)).toBe(true)
  })

  it('says no for another club key, a public key or rubbish', async () => {
    const priv = await generateX25519Identity()
    const pub = await identityToRecipient(priv)
    const other = await generateX25519Identity()
    expect(await keyFileMatches(other, pub)).toBe(false)
    expect(await keyFileMatches(pub, pub)).toBe(false)
    expect(await keyFileMatches('AGE-SECRET-KEY-1NOPE', pub)).toBe(false)
    expect(await keyFileMatches('', pub)).toBe(false)
  })
})
