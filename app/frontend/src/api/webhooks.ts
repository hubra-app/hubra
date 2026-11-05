import { apiFetch } from '@hubra/api-client'

/** An address the club's own tool listens on (docs/webhooks.md). */
export interface Webhook {
  id: number
  name: string
  url: string
  events: string[]
  active: boolean
  /** Failed deliveries in a row; at 20 the webhook switches itself off. */
  failures: number
  disabledReason: string | null
  createdAt: string
  lastDeliveryAt: string | null
  /** Only in the answer that creates it or makes a new one. */
  secret?: string
}

export interface WebhookDelivery {
  id: number
  uid: string
  event: string
  status: 'pending' | 'delivered' | 'failed'
  attempts: number
  responseStatus: number | null
  error: string | null
  durationMs: number | null
  createdAt: string
  lastAttemptAt: string | null
}

export interface WebhookInput {
  name: string
  url: string
  events: string[]
}

const base = '/app/webhooks'

export function listWebhooks(): Promise<{ items: Webhook[]; events: string[]; max: number }> {
  return apiFetch(`${base}/`)
}

export function createWebhook(input: WebhookInput): Promise<Webhook> {
  return apiFetch(`${base}/`, { method: 'POST', body: JSON.stringify(input) })
}

export function updateWebhook(id: number, input: Partial<WebhookInput> & { active?: boolean }): Promise<Webhook> {
  return apiFetch(`${base}/${id}`, { method: 'PATCH', body: JSON.stringify(input) })
}

export async function deleteWebhook(id: number): Promise<void> {
  await apiFetch(`${base}/${id}`, { method: 'DELETE' })
}

export function rollWebhookSecret(id: number): Promise<Webhook> {
  return apiFetch(`${base}/${id}/secret`, { method: 'POST' })
}

export function testWebhook(id: number): Promise<WebhookDelivery> {
  return apiFetch(`${base}/${id}/test`, { method: 'POST' })
}

export function listWebhookDeliveries(id: number): Promise<{ items: WebhookDelivery[] }> {
  return apiFetch(`${base}/${id}/deliveries`)
}

export function retryWebhookDelivery(id: number): Promise<WebhookDelivery> {
  return apiFetch(`${base}/deliveries/${id}/retry`, { method: 'POST' })
}
