// Passkeys in the browser: the API sends WebAuthn options as JSON
// (binary fields base64url), the browser wants ArrayBuffers, and back.

type Json = Record<string, unknown>

function fromB64url(value: string): ArrayBuffer {
  const b64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4))
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes.buffer
}

function toB64url(buffer: ArrayBuffer | null | undefined): string | undefined {
  if (!buffer) return undefined
  const bytes = new Uint8Array(buffer)
  let raw = ''
  for (const b of bytes) raw += String.fromCharCode(b)
  return btoa(raw).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function descriptors(list: unknown): PublicKeyCredentialDescriptor[] | undefined {
  if (!Array.isArray(list)) return undefined
  return list.map((d: Json) => ({
    type: 'public-key',
    id: fromB64url(d.id as string),
    transports: d.transports as AuthenticatorTransport[] | undefined,
  }))
}

export function passkeysSupported(): boolean {
  return typeof window !== 'undefined' && 'PublicKeyCredential' in window && !!navigator.credentials
}

/** True when the person closed the browser's passkey dialog. */
export function passkeyCancelled(err: unknown): boolean {
  return err instanceof DOMException && (err.name === 'NotAllowedError' || err.name === 'AbortError')
}

export async function createPasskey(options: Json): Promise<Json> {
  const user = options.user as Json
  const publicKey: PublicKeyCredentialCreationOptions = {
    ...(options as unknown as PublicKeyCredentialCreationOptions),
    challenge: fromB64url(options.challenge as string),
    user: { ...(user as unknown as PublicKeyCredentialUserEntity), id: fromB64url(user.id as string) },
    excludeCredentials: descriptors(options.excludeCredentials),
  }
  const cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential
  const res = cred.response as AuthenticatorAttestationResponse
  return {
    id: cred.id,
    rawId: toB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: toB64url(res.clientDataJSON),
      attestationObject: toB64url(res.attestationObject),
      transports: typeof res.getTransports === 'function' ? res.getTransports() : [],
    },
    clientExtensionResults: cred.getClientExtensionResults(),
    authenticatorAttachment: cred.authenticatorAttachment ?? undefined,
  }
}

export async function getPasskey(options: Json): Promise<Json> {
  const publicKey: PublicKeyCredentialRequestOptions = {
    ...(options as unknown as PublicKeyCredentialRequestOptions),
    challenge: fromB64url(options.challenge as string),
    allowCredentials: descriptors(options.allowCredentials),
  }
  const cred = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential
  const res = cred.response as AuthenticatorAssertionResponse
  return {
    id: cred.id,
    rawId: toB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: toB64url(res.clientDataJSON),
      authenticatorData: toB64url(res.authenticatorData),
      signature: toB64url(res.signature),
      userHandle: toB64url(res.userHandle),
    },
    clientExtensionResults: cred.getClientExtensionResults(),
    authenticatorAttachment: cred.authenticatorAttachment ?? undefined,
  }
}
