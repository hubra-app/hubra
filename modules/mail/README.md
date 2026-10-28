# Mail Stack

Fully self-hosted mail stack using [WildDuck](https://github.com/nodemailer/wildduck) (IMAP), Haraka (inbound SMTP), and ZoneMTA (outbound SMTP). All mail data lives in MongoDB; queue state lives in Redis.

## Deployment

The mail stack is **opt-in** and lives in `modules/mail/docker-compose.mail.yml`. The default
`docker compose up -d` runs only the app stack.

```bash
# App stack only (default)
docker compose up -d

# App + mail stack
docker compose -f docker-compose.yml -f modules/mail/docker-compose.mail.yml up -d
```

Prerequisites:

- the mail module switched on: `docker compose exec backend flask modules enable mail`
- Mail-related env vars set in `.env` (`WILDDUCK_API_TOKEN`, `LOOP_SECRET`,
  `SRS_SECRET`, `REWRITE_DOMAIN`, `ACME_EMAIL`, `MAIL_HOST`, etc.)
- `./modules/mail/certbot/cloudflare.ini` present with Cloudflare API credentials

All 8 mail services (`mongo`, `mailserver`, `haraka`, `zonemta`, `certbot-init`,
`certbot-renew`, `cert-watcher`, `socket-proxy`) are defined in
`docker-compose.mail.yml`. The `modules/mail/` directory contains their build contexts
and config templates.

## Architecture

```
         Internet (sending MTA)
                  │
              port 25
                  ▼
         ┌──────────────┐
         │   Haraka      │  Inbound SMTP
         │  (inbound)    │  SRS rewrite
         └──────┬───────┘
                │ delivery
                ▼
         ┌──────────────┐
         │  WildDuck     │  IMAP server
         │  (mail store) │  REST API :8080
         └──────┬───────┘
                │ forwarding
                ▼
         ┌──────────────┐
         │   ZoneMTA     │  Outbound SMTP
         │  (outbound)   │  port 465/587
         └──────┬───────┘
                │
         Internet (Gmail, Outlook, etc.)

Member mailbox:  member@club.ch  ← IMAP (143/993)
Group alias:     events@club.ch  → forwards to member mailboxes
Forwarding:      member@club.ch  → someone@gmail.com (optional, per-user)
```

## Services

| Service           | Container                     | Ports                               | Role                                                          |
| ----------------- | ----------------------------- | ----------------------------------- | ------------------------------------------------------------- |
| **WildDuck**      | `ghcr.io/zone-eu/wildduck`    | 143 (IMAP), 993 (IMAPS), 8080 (API) | Mail storage, IMAP access, REST API for user/alias management |
| **Haraka**        | Custom (`modules/mail/haraka/`)       | 25 (SMTP)                           | Inbound SMTP, SRS rewriting, passes to WildDuck for delivery  |
| **ZoneMTA**       | Custom (`modules/mail/zonemta/`)      | 465 (SMTPS), 587 (STARTTLS)         | Outbound SMTP, DKIM-ready, relay to external providers        |
| **certbot-init**  | `certbot/dns-cloudflare`      | —                                   | One-shot TLS cert issuance via DNS-01                         |
| **certbot-renew** | `certbot/dns-cloudflare`      | —                                   | Renews certs every 12 hours                                   |
| **cert-watcher**  | Custom (`modules/mail/cert-watcher/`) | —                                   | Monitors cert files, restarts mail services on renewal        |

## Mail flow

**Inbound (received from external MTA):**

1. External server sends to MX record → port 25 → Haraka
2. Haraka performs SRS rewrites, delivers to WildDuck via LMTP
3. WildDuck stores in recipient's mailbox (MongoDB)
4. If forwarding is enabled, WildDuck passes to ZoneMTA for outbound relay

**Outbound (sent by member via IMAP/SMTP):**

1. Member connects to ZoneMTA on port 465 (SMTPS) or 587 (STARTTLS)
2. ZoneMTA authenticates against WildDuck user credentials
3. ZoneMTA queues message in MongoDB, delivers to external MTA
4. SRS rewriting applied for bounce handling

## Forwarding model

Forwarding is **1-way, per-user opt-in, never group-driven**.

- **Default**: forwarding disabled. Mail stays in the club mailbox.
- **Enabled**: mail is both stored in the club mailbox AND forwarded to the member's private email (mirror mode).
- **Group aliases**: always deliver to club mailboxes only — never directly to private emails.

```
                     ┌──────────────┐
Group alias ────────►│  Club mailbox │──► IMAP (member reads here)
  events@club.ch     │  member@club  │
                     └──────┬───────┘
                            │ forwarding (optional)
                            ▼
                     ┌──────────────┐
                     │  Private email│
                     │  mike@gmail   │
                     └──────────────┘
```

## Key components

| File                                         | Purpose                                                                                                                |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `app/backend/hubra/core/services/wildduck.py`| HTTP client for WildDuck REST API (users, addresses, forwarding aliases, messages)                                     |
| `app/backend/hubra/core/tasks/wildduck.py`| Celery tasks for async provisioning (user creation, password sync, mailbox enable/disable, group aliases, send-as ACL) |
| `app/backend/hubra/core/tasks/mail_tasks.py`| Periodic Celery tasks (retention cleanup daily, mailbox reconciliation every 5 min)                                    |
| `app/backend/hubra/api/mail/routes.py`   | REST endpoints: mailboxes CRUD, aliases CRUD, member mail provisioning, test email                                     |

### Celery tasks in `tasks/wildduck.py`

| Task                               | Trigger                                  | Purpose                                        |
| ---------------------------------- | ---------------------------------------- | ---------------------------------------------- |
| `create_wildduck_user`             | Member created with mailbox_enabled=True | Creates WildDuck mailbox                       |
| `sync_wildduck_password`           | Password change                          | Syncs password hash to WildDuck                |
| `provision_member_mail`            | Mailbox/forwarding flag change           | Applies mailbox_enabled/forwarding flags       |
| `provision_group_alias`            | Group created/renamed/deleted            | Creates/updates/removes group forwarding alias |
| `sync_group_alias`                 | Group membership added/removed           | Rebuilds alias target list                     |
| `grant_send_as` / `revoke_send_as` | (Stubbed)                                | Manages send-as ACL                            |

### Periodic tasks in `hubra/core/tasks/mail_tasks.py`

| Task                  | Schedule         | Purpose                                                          |
| --------------------- | ---------------- | ---------------------------------------------------------------- |
| `retention_cleanup`   | Daily 02:00 UTC  | Deletes messages older than per-member retention period          |
| `reconcile_mail`      | Every 15 minutes | Creates missing addresses, syncs every address to WildDuck       |
| `check_mailbox_quota` | Hourly           | Alerts owner and postmaster when a mailbox is 90% full           |

## TLS

| Service          | Port | Protocol                                  |
| ---------------- | ---- | ----------------------------------------- |
| Haraka inbound   | 25   | Plaintext (see ISSUE-071 for TLS)         |
| ZoneMTA outbound | 465  | SMTPS (TLS implicit)                      |
| ZoneMTA outbound | 587  | STARTTLS                                  |
| WildDuck IMAP    | 143  | STARTTLS                                  |
| WildDuck IMAPS   | 993  | IMAPS (TLS implicit)                      |
| WildDuck API     | 8080 | Plain HTTP (internal Docker network only) |

- Certificates obtained via certbot DNS-01 challenge (Cloudflare)
- Auto-renewed every 12 hours
- `cert-watcher` monitors `/etc/letsencrypt/live` and restarts services on renewal

## Running on k3s

The module ships its own manifests in `modules/mail/k8s/`. They're off unless
you deploy that directory next to `deploy/app` (a second Kustomization in your
GitOps tool, or `kubectl apply -k`). Prerequisites are the same as for
Compose, plus the general setup in [docs/k3s.md](../../docs/k3s.md).

- **Host ports.** IMAPS 993, SMTP 25 and submission 465/587 are `LoadBalancer`
  Services. k3s ServiceLB binds them on the node with
  `externalTrafficPolicy: Local`, so Haraka sees real sender IPs. Stop the
  Compose mail containers first, or the ports collide.
- **Certificates.** certbot still writes `/etc/letsencrypt/live/$MAIL_HOST/*` to a
  shared volume, so the Haraka, ZoneMTA and WildDuck config is unchanged.
  `create-secrets.sh` turns `certbot/cloudflare.ini` into Secret
  `cloudflare-credentials`. Mail pods wait until the cert exists.
- **Reload on renewal.** cert-watcher and socket-proxy are Compose-only. On k3s
  the `mail-cert-reload` CronJob checks hourly and restarts `mailserver`,
  `haraka` and `zonemta` when `fullchain.pem` changes. Its first run restarts
  them once.
- **Single node.** The `letsencrypt` volume is shared by several pods, which
  works because they all run on the same node.
- **Data from Compose.** Copy Mongo with `mongodump --archive` /
  `mongorestore --archive` (via `kubectl exec -i mongo-0`). Copy the `mail_data`
  and `letsencrypt` Docker volumes into the `mail-data` and `letsencrypt` PVCs,
  which live under `/var/lib/rancher/k3s/storage/` on the node.

Known issue, unchanged by the move: Haraka's `wildduck.yaml` and ZoneMTA's
Mongo/Redis URLs carry no credentials, while Mongo runs with root auth and Redis
with `requirepass`.
