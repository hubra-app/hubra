# Hubra — Backend API

Base URL: `https://api.vollbuild.ch/api/v1` (production)
Auth: JWT cookies (`HttpOnly`, `Domain=.vollbuild.ch`, `SameSite=Lax`)
Content-Type: `application/json`

---

## Database

**PostgreSQL** — relational, with foreign keys and linking tables.

### Linking tables

| Table               | Columns                    | Purpose                    |
| ------------------- | -------------------------- | -------------------------- |
| `member_groups`     | `member_id`, `group_id`    | M:N — members ↔ groups     |
| `member_categories` | `member_id`, `category_id` | M:N — members ↔ categories |
| `event_attendees`   | `event_id`, `member_id`    | M:N — events ↔ attendees   |

All other relationships are FK columns on the owning table (e.g. `Group.lead_id → members.id`, `Invoice.member_id → members.id`).

### Default rows

Certain seed rows carry `is_default = true`. These rows **cannot be deleted** — the API returns `409 CONFLICT` if deletion is attempted. New rows can always be created and deleted freely.

| Table                    | Default rows                                                          |
| ------------------------ | --------------------------------------------------------------------- |
| `transaction_categories` | Membership, Events, Consumables, Utilities, Donation, Other           |
| `roles`                  | Admin, Manager, Treasurer, Member                                     |
| `groups`                 | Pre-seeded workshop groups (Woodshop, Laser & CNC, 3D Printing, etc.) |

---

## Authentication

| Method | Path                       | Auth        | Description                                                  |
| ------ | -------------------------- | ----------- | ------------------------------------------------------------ |
| POST   | `/auth/login`              | —           | Email + password → JWT + refresh token                       |
| POST   | `/auth/refresh`            | Refresh JWT | Rotate access token                                          |
| POST   | `/auth/logout`             | Bearer JWT  | Invalidate tokens                                            |
| POST   | `/auth/bootstrap`          | —           | First-run setup — creates club settings + first Admin member |
| POST   | `/auth/forgot-password`    | —           | Request a password reset email                               |
| POST   | `/auth/reset-password`     | —           | Set a new password using a reset token                       |
| GET    | `/account`                 | Bearer JWT  | Get current member's profile                                 |
| PATCH  | `/account`                 | Bearer JWT  | Update name, email, or password (first-login forced reset)   |
| POST   | `/account/change-password` | Bearer JWT  | Voluntarily change password (requires current password)      |

**Login request**

```json
{ "email": "string", "password": "string" }
```

**Login response**

```json
{ "accessToken": "string", "refreshToken": "string", "member": { ...Member } }
```

If the login IP differs from the previous login, a new-device alert email is sent to the member.

The first member created during bootstrap is automatically assigned `role: "Admin"`. Admins are regular members — there is no separate user model.

---

### Password Reset

**Request a reset link**

```
POST /auth/forgot-password
```

```json
{ "email": "member@example.com" }
```

Always returns `200 { "ok": true }` — the email address is never confirmed or denied in the response to prevent enumeration. An email containing a one-time link is sent if the address belongs to an active member. The token expires after **1 hour** and is single-use. Any previously-issued unused tokens for the same member are invalidated.

**Reset the password**

```
POST /auth/reset-password
```

```json
{ "token": "string", "password": "string" }
```

| Field      | Rules                                     |
| ---------- | ----------------------------------------- |
| `token`    | Raw token from the reset URL (`?token=…`) |
| `password` | Minimum 8 characters                      |

Returns `200 { "ok": true }` on success. A confirmation email is sent to the member.

Errors:

| Code               | Status | Meaning                                   |
| ------------------ | ------ | ----------------------------------------- |
| `VALIDATION_ERROR` | 400    | Missing field or password too short       |
| `INVALID_TOKEN`    | 400    | Token not found, already used, or expired |

---

### Change Password (authenticated)

```
POST /account/change-password
```

```json
{ "currentPassword": "string", "newPassword": "string" }
```

Requires a valid Bearer JWT. Verifies `currentPassword` against the stored hash before updating. A confirmation email is sent on success. WildDuck password is synced if a mailbox exists.

| Field             | Rules                       |
| ----------------- | --------------------------- |
| `currentPassword` | Must match current password |
| `newPassword`     | Minimum 8 characters        |

Errors:

| Code               | Status | Meaning                                 |
| ------------------ | ------ | --------------------------------------- |
| `VALIDATION_ERROR` | 400    | Missing field or new password too short |
| `UNAUTHORIZED`     | 401    | Current password is incorrect           |

---

### Email Notifications (account events)

Outbound emails are sent via Brevo. All sends are non-blocking — failures are logged but never surface as API errors.

| Event               | Trigger                                             | Template                              |
| ------------------- | --------------------------------------------------- | ------------------------------------- |
| Welcome             | Admin creates a new member                          | Login credentials                     |
| Password reset      | `POST /auth/forgot-password`                        | One-time reset link (1 h expiry)      |
| Password changed    | Successful reset or `POST /account/change-password` | Confirmation with support link        |
| New device login    | Login IP differs from last recorded IP              | IP, browser, timestamp                |
| Account deactivated | `DELETE /members/<id>`                              | Deactivation notice with support link |

**Self-deletion prevention**

`DELETE /members/<id>` returns `403 SELF_DELETE` if the authenticated member attempts to deactivate their own account. The frontend suppresses the delete button entirely on the actor's own row — the backend check is the authoritative guard.

Sender name and email address are configured in the club settings (`notification_sender_name`, `notification_sender_email`).

---

## Models

All `id` fields are auto-incremented database integers. Foreign keys reference those integer IDs and are resolved to their full objects (or a summary) in GET responses.

### Role

```ts
{
  id: int;
  name: string; // e.g. "Admin", "Manager", "Treasurer", "Member"
  isDefault: boolean; // true = seeded, cannot be deleted
}
```

### Member

```ts
{
  id: int
  name: string
  email: string          // private email, editable by member
  publicEmail: string    // club domain email, read-only
  tierId: int            // FK → MembershipTier
  groupIds: int[]        // via member_groups linking table
  roleId: int            // FK → Role
  joined: string         // ISO date "YYYY-MM-DD"
  lastSeen: string       // ISO date
  status: "active" | "trial" | "inactive" | "suspended"
  toolHours: int
  notes: string
  categoryIds: int[]     // via member_categories linking table
  avatarColor: string    // hex
}
```

### MembershipTier

```ts
{
  id: int;
  name: string; // e.g. "Maker", "Pro"
  priceChf: number;
  color: string; // hex
}
```

### Category

```ts
{
  id: int;
  name: string;
  description: string;
  color: string; // hex
  memberCount: int; // computed
}
```

### Application

```ts
{
  id: int;
  name: string;
  email: string;
  wantsTierId: int; // FK → MembershipTier
  appliedAt: string; // ISO datetime
  avatarColor: string; // hex
}
```

### Group

```ts
{
  id: int;
  name: string;
  leadId: int; // FK → Member, resolved to member object on read
  description: string;
  color: string; // hex
  iconName: string; // lucide icon name
  memberCount: int; // computed
  sessions: string; // e.g. "3x/week"
  tools: int;
  isDefault: boolean; // true = seeded, cannot be deleted
}
```

### TransactionCategory

```ts
{
  id: int;
  name: string; // e.g. "Membership", "Events"
  color: string; // hex
  isDefault: boolean; // true = seeded, cannot be deleted
}
```

### ClubEvent

```ts
{
  id: int
  title: string
  date: string           // ISO date
  time: string           // e.g. "14:00-18:00"
  location: string
  type: "Workshop" | "Social" | "Certification" | "Meeting"
  attendeeIds: int[]     // FK[] → Member
}
```

### Poll

```ts
{
  id: int;
  question: string;
  options: {
    label: string;
    votes: int;
  }
  [];
  totalVotes: int; // computed
  closesAt: string; // ISO datetime
  status: "open" | "closed";
}
```

### Transaction

```ts
{
  id: int;
  date: string; // ISO date
  description: string;
  categoryId: int; // FK → TransactionCategory
  memberId: int | null; // FK → Member; null for batch / non-member payees
  payeeName: string; // display name when memberId is null
  amount: number; // positive = income, negative = expense
  method: "IBAN" | "Card" | "Twint" | "Cash";
  type: "income" | "expense";
}
```

### Invoice

```ts
{
  id: int;
  memberId: int; // FK → Member
  issued: string; // ISO date
  due: string; // ISO date
  amount: number;
  status: "Paid" | "Open" | "Overdue";
}
```

### Mailbox

```ts
{
  id: int;
  address: string; // e.g. "info@vollbuild.ch"
  displayName: string;
  messageCount: int;
  quotaUsed: number; // GB
  quotaTotal: number; // GB
  sendOnly: boolean;
}
```

### Alias

```ts
{
  id: int
  address: string
  type: "Alias" | "Forward" | "Distribution"
  deliversTo: string[]   // resolved email addresses
  enabled: boolean
}
```

### MailLogEntry

```ts
{
  id: int;
  direction: "inbound" | "outbound";
  from: string;
  to: string;
  subject: string;
  time: string; // ISO datetime
  sizeBytes: int;
  status: "Delivered" | "Bounced" | "Deferred" | "Rejected" | "Spam";
}
```

### AuditEntry

```ts
{
  id: int;
  actorId: int; // FK → Member
  action: string;
  targetType: string; // e.g. "Member", "Invoice", "Group"
  targetId: int;
  targetLabel: string; // human-readable snapshot at time of action
  time: string; // ISO datetime
}
```

### Notification

```ts
{
  id: int;
  memberId: int; // FK → Member (recipient)
  kind: "info" | "success" | "warning" | "member";
  title: string;
  msg: string;
  time: string; // ISO datetime
  read: boolean;
}
```

---

## Roles

| Method | Path         | Description                                                                      |
| ------ | ------------ | -------------------------------------------------------------------------------- |
| GET    | `/roles`     | List all roles                                                                   |
| POST   | `/roles`     | Create role                                                                      |
| PATCH  | `/roles/:id` | Rename role                                                                      |
| DELETE | `/roles/:id` | Delete role (fails with 409 if `isDefault = true` or any member holds this role) |

---

## Transaction Categories

| Method | Path                          | Description                                                                             |
| ------ | ----------------------------- | --------------------------------------------------------------------------------------- |
| GET    | `/transaction-categories`     | List all categories                                                                     |
| POST   | `/transaction-categories`     | Create category                                                                         |
| PATCH  | `/transaction-categories/:id` | Update name or color                                                                    |
| DELETE | `/transaction-categories/:id` | Delete category (fails with 409 if `isDefault = true` or any transaction references it) |

---

## Members

| Method | Path              | Description                   |
| ------ | ----------------- | ----------------------------- |
| GET    | `/members`        | List all members (filterable) |
| GET    | `/members/:id`    | Get single member             |
| POST   | `/members`        | Create member                 |
| PATCH  | `/members/:id`    | Update member fields          |
| DELETE | `/members/:id`    | Delete member                 |
| GET    | `/members/export` | Export CSV                    |

**GET /members query params**

- `search` — name/email fulltext
- `status` — active / trial / inactive / suspended
- `tier` — tier name
- `group` — group name
- `category` — category name
- `page`, `pageSize`

---

## Membership Tiers

| Method | Path         | Description                             |
| ------ | ------------ | --------------------------------------- |
| GET    | `/tiers`     | List all tiers                          |
| POST   | `/tiers`     | Create tier                             |
| PATCH  | `/tiers/:id` | Update tier (name, price, color)        |
| DELETE | `/tiers/:id` | Delete tier (only if no active members) |

---

## Categories

| Method | Path                                | Description                 |
| ------ | ----------------------------------- | --------------------------- |
| GET    | `/categories`                       | List all categories         |
| POST   | `/categories`                       | Create category             |
| PATCH  | `/categories/:id`                   | Update category             |
| DELETE | `/categories/:id`                   | Delete category             |
| POST   | `/categories/:id/members/:memberId` | Add member to category      |
| DELETE | `/categories/:id/members/:memberId` | Remove member from category |

---

## Applications

| Method | Path                        | Description                  |
| ------ | --------------------------- | ---------------------------- |
| GET    | `/applications`             | List pending applications    |
| GET    | `/applications/:id`         | Get single application       |
| POST   | `/applications/:id/approve` | Approve and create member    |
| POST   | `/applications/:id/decline` | Decline with optional reason |
| DELETE | `/applications/:id`         | Delete application           |

**POST /applications/:id/approve body**

```json
{ "tierId": 1, "role": "Member" }
```

---

## Groups

| Method | Path          | Description             |
| ------ | ------------- | ----------------------- |
| GET    | `/groups`     | List all groups         |
| GET    | `/groups/:id` | Get group + member list |
| POST   | `/groups`     | Create group            |
| PATCH  | `/groups/:id` | Update group            |
| DELETE | `/groups/:id` | Delete group            |

---

## Events

| Method | Path                              | Description           |
| ------ | --------------------------------- | --------------------- |
| GET    | `/events`                         | List events           |
| GET    | `/events/:id`                     | Get event + attendees |
| POST   | `/events`                         | Create event          |
| PATCH  | `/events/:id`                     | Update event          |
| DELETE | `/events/:id`                     | Delete event          |
| POST   | `/events/:id/attendees/:memberId` | Add attendee          |
| DELETE | `/events/:id/attendees/:memberId` | Remove attendee       |

**GET /events query params**

- `from`, `to` — ISO date range
- `type` — Workshop / Social / Certification / Meeting

---

## Polls

| Method | Path               | Description        |
| ------ | ------------------ | ------------------ |
| GET    | `/polls`           | List polls         |
| GET    | `/polls/:id`       | Get poll + results |
| POST   | `/polls`           | Create poll        |
| POST   | `/polls/:id/vote`  | Cast vote          |
| PATCH  | `/polls/:id/close` | Close poll         |
| DELETE | `/polls/:id`       | Delete poll        |

**POST /polls/:id/vote body**

```json
{ "optionIndex": 0 }
```

---

## Posts

| Method | Path                             | Description                              |
| ------ | -------------------------------- | ---------------------------------------- |
| GET    | `/posts`                         | List posts (newest first)                |
| GET    | `/posts/:id`                     | Get post with like count + comment count |
| POST   | `/posts`                         | Create post (manager/admin)              |
| PATCH  | `/posts/:id`                     | Update post (author or admin)            |
| DELETE | `/posts/:id`                     | Delete post (author or admin)            |
| POST   | `/posts/:id/like`                | Like a post (409 if already liked)       |
| DELETE | `/posts/:id/like`                | Unlike a post (404 if not liked)         |
| GET    | `/posts/:id/comments`            | List comments for a post                 |
| POST   | `/posts/:id/comments`            | Add a comment                            |
| DELETE | `/posts/:id/comments/:commentId` | Delete a comment (author or admin)       |

**POST /posts body**

```json
{
  "title": "New dust extractor installed!",
  "summary": "Quick update",
  "body": "Full text..."
}
```

**POST /posts/:id/comments body**

```json
{ "body": "Great news!" }
```

---

## Finances — Transactions

| Method | Path                | Description        |
| ------ | ------------------- | ------------------ |
| GET    | `/transactions`     | List transactions  |
| POST   | `/transactions`     | Record transaction |
| DELETE | `/transactions/:id` | Delete transaction |

**GET /transactions query params**

- `search`
- `type` — income / expense
- `category`
- `from`, `to` — ISO date range
- `page`, `pageSize`

---

## Finances — Invoices

| Method | Path                   | Description                     |
| ------ | ---------------------- | ------------------------------- |
| GET    | `/invoices`            | List invoices                   |
| POST   | `/invoices`            | Create invoice                  |
| PATCH  | `/invoices/:id`        | Update invoice (e.g. mark paid) |
| DELETE | `/invoices/:id`        | Delete invoice                  |
| POST   | `/invoices/:id/remind` | Send payment reminder email     |

**GET /invoices query params**

- `status` — Paid / Open / Overdue
- `member`
- `page`, `pageSize`

---

## Mail — Mailboxes

| Method | Path                  | Description                                |
| ------ | --------------------- | ------------------------------------------ |
| GET    | `/mail/mailboxes`     | List mailboxes + quota stats               |
| POST   | `/mail/mailboxes`     | Create mailbox (provisions on mail server) |
| PATCH  | `/mail/mailboxes/:id` | Update display name or quota               |
| DELETE | `/mail/mailboxes/:id` | Delete mailbox                             |

---

## Mail — Aliases

| Method | Path                | Description                          |
| ------ | ------------------- | ------------------------------------ |
| GET    | `/mail/aliases`     | List aliases                         |
| POST   | `/mail/aliases`     | Create alias                         |
| PATCH  | `/mail/aliases/:id` | Update alias (destinations, enabled) |
| DELETE | `/mail/aliases/:id` | Delete alias                         |

---

## Mail — Message Log

| Method | Path                      | Description                    |
| ------ | ------------------------- | ------------------------------ |
| GET    | `/mail/log`               | List log entries               |
| GET    | `/mail/log/:id`           | Get full trace for one message |
| POST   | `/mail/log/:id/redeliver` | Re-queue failed message        |
| POST   | `/mail/test`              | Send test email                |

**GET /mail/log query params**

- `search` — from/to/subject fulltext
- `direction` — inbound / outbound
- `status` — Delivered / Bounced / Deferred / Rejected / Spam
- `from`, `to` — ISO datetime range
- `page`, `pageSize`

---

## Settings

| Method | Path        | Description           |
| ------ | ----------- | --------------------- |
| GET    | `/settings` | Get all club settings |
| PATCH  | `/settings` | Update club settings  |

**Settings object**

```ts
{
  clubName: string;
  domain: string;
  currency: string; // "CHF"
  defaultTier: string;
  spfRecord: string;
  dkimEnabled: boolean;
  dmarcPolicy: string;
}
```

---

## Account (current member)

The authenticated member's own profile. Equivalent to `GET /members/:id` for the current session, but with write access restricted to personal fields only.

| Method | Path       | Description                                            |
| ------ | ---------- | ------------------------------------------------------ |
| GET    | `/account` | Get current member profile                             |
| PATCH  | `/account` | Update personal fields (name, private email, password) |

**PATCH /account — allowed fields only**

```json
{ "name": "string", "email": "string", "password": "string" }
```

`publicEmail` is system-assigned (derived from club domain) and is never accepted in this endpoint. To change it, an Admin must update it via `PATCH /members/:id`.

---

## Notifications

| Method | Path                      | Description                         |
| ------ | ------------------------- | ----------------------------------- |
| GET    | `/notifications`          | List notifications for current user |
| PATCH  | `/notifications/:id/read` | Mark one as read                    |
| POST   | `/notifications/read-all` | Mark all as read                    |
| DELETE | `/notifications/:id`      | Delete notification                 |

---

## Audit Log

| Method | Path     | Description                    |
| ------ | -------- | ------------------------------ |
| GET    | `/audit` | List audit entries (read-only) |

**GET /audit query params**

- `actorId` — filter by member ID
- `from`, `to` — ISO datetime range
- `page`, `pageSize`

Audit entries are written automatically by the backend on every mutating operation and cannot be created or modified via the API.

---

## Pagination envelope

All paginated list endpoints return:

```json
{
  "data": [...],
  "total": 123,
  "page": 1,
  "pageSize": 25,
  "totalPages": 5
}
```

Default `pageSize`: 25. Maximum: 100.

---

## Error format

```json
{
  "error": "NOT_FOUND",
  "message": "Member M-099 does not exist"
}
```

| HTTP | Error code                           |
| ---- | ------------------------------------ |
| 400  | VALIDATION_ERROR                     |
| 401  | UNAUTHORIZED                         |
| 403  | FORBIDDEN                            |
| 404  | NOT_FOUND                            |
| 409  | CONFLICT (e.g. email already in use) |
| 500  | INTERNAL_ERROR                       |
