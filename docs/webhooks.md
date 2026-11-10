# Outgoing webhooks

A club can tell its own tools what happens in Hubra: a newsletter tool learns
about a new member, a spreadsheet hears that an invoice was paid, Zapier or
n8n start a flow when an event is published. Hubra sends each change as a
signed `POST` to an https address the club chooses.

Club admins set them up under **Settings › API & Webhooks › Webhooks**. A club has
at most 10 webhooks. API tokens can't read or change webhooks: a token must
not be able to send the club's data to an address of its choosing.

## Setting one up

1. **New webhook**: give it a name, the https address of your tool and the
   events it should hear about.
2. Hubra shows the **signing secret** (`whsec_…`) once. Put it into your tool;
   afterwards it can only be replaced (**New secret**, the old one stops at
   once).
3. **Send test** sends a `ping` right away and shows the answer.
4. **History** lists the last 50 deliveries with status, answer and time. A
   failed one can be sent again with **Retry**.

Only public https addresses are allowed. Hubra looks the host up before
every call and refuses private, local and reserved addresses, connects to
the address it checked, and doesn't follow redirects.

## Events

| Event | When | `data` |
| --- | --- | --- |
| `member.joined` | An account was added to the club, an application was approved, or a former member came back | `member_id` |
| `member.left` | A member was archived, left, or was deleted | `member_id` |
| `invoice.created` | An invoice was created | `invoice_id`, `category_id` |
| `invoice.paid` | An invoice was marked paid | `invoice_id`, `member_id` |
| `invoice.overdue` | The first reminder for an invoice went out | `invoice_id`, `member_id` |
| `invoice.deleted` | An invoice was deleted | `invoice_id`, `transaction_id` |
| `event.published` | An event was published | `event_id` |
| `event.changed` | An event was changed, called off or deleted (one per date of a series) | `event_id`, `deleted` when it is gone, `cancelled` and `reason` when it was called off (`cancelled: false` when it takes place again) |
| `post.published` | A post was published | `post_id` |
| `poll.published` | A poll was published | `poll_id` |
| `poll.closed` | An organiser closed a poll early | `poll_id` |
| `group.membership_changed` | Someone joined or left a group | `group_id`, `member_id`, `action` |
| `ping` | **Send test** | `webhookId` |

## What your tool receives

```http
POST /your/path HTTP/1.1
Content-Type: application/json
User-Agent: Hubra-Webhooks/1
X-Hubra-Event: member.joined
X-Hubra-Delivery: 4b0c2b6e-0f3a-4c9e-9a59-5d0c6a1f7f21
X-Hubra-Signature: t=1762365600,v1=5f2c…

{
  "id": "4b0c2b6e-0f3a-4c9e-9a59-5d0c6a1f7f21",
  "event": "member.joined",
  "createdAt": "2026-11-05T18:00:00+00:00",
  "club": {"slug": "fc-demo", "name": "FC Demo"},
  "data": {"member_id": 42},
  "object": {
    "id": 42,
    "firstName": "Anna",
    "lastName": "Muster",
    "email": "anna@example.com",
    "status": "active",
    "membershipType": "active",
    "tier": "Adults",
    "joined": "2026-11-05",
    "left": null
  }
}
```

`object` is the thing the event is about, as it was when the message was
built: a member, an invoice (`id`, `memberId`, `amount`, `status`, `issued`,
`due`, `description`), an event (`id`, `title`, `date`, `time`, `location`,
`public`), a post (`id`, `title`) or a poll (`id`, `question`, `status`). It
is `null` for a deleted invoice or event, for group changes and for `ping`.

`X-Hubra-Delivery` (and `id`) stays the same when a delivery is retried, so
your tool can ignore a message it already handled.

## Checking the signature

`X-Hubra-Signature` is `t=<unix seconds>,v1=<hex>`, where `<hex>` is the
HMAC-SHA256 of `"<t>." + <raw body>` with the secret as key. Check it on the
raw body, before parsing the JSON, and reject old timestamps (5 minutes is a
good limit) so a recorded message can't be replayed.

```python
import hashlib, hmac, time

def verify(secret: str, header: str, body: bytes, tolerance: int = 300) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    ts = int(parts["t"])
    if abs(time.time() - ts) > tolerance:
        return False
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), parts["v1"])
```

```js
import crypto from 'node:crypto'

function verify(secret, header, rawBody, tolerance = 300) {
  const parts = Object.fromEntries(header.split(',').map((p) => p.split('=')))
  if (Math.abs(Date.now() / 1000 - Number(parts.t)) > tolerance) return false
  const mac = crypto.createHmac('sha256', secret).update(`${parts.t}.`).update(rawBody).digest('hex')
  return crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(parts.v1))
}
```

## Answers, retries and switching off

Answer with any `2xx` within 5 seconds; do slow work afterwards. Anything
else (another status, a timeout, no connection) counts as failed and is
sent again after 1 minute, 10 minutes and 1 hour. A `ping` is not retried.
If a retry is lost (Redis restarted), a sweep every five minutes sends the
deliveries that are more than five minutes overdue.

After 20 failed deliveries in a row the webhook switches itself off and
says so in the settings. Fix the address and switch it back on; that resets
the count.

Messages are sent by the worker after the change is saved, so a slow or
broken receiver never holds up the person who made the change. Hubra keeps
the last 50 deliveries of each webhook.

## For operators

Run `flask db upgrade` (tables `webhooks` and `webhook_deliveries` in each
club schema). Secrets are stored encrypted with `FERNET_KEY`. The worker and
Redis must be running for deliveries and retries. The module `webhooks` is on
by default; switching it off in a club stops all its deliveries.
