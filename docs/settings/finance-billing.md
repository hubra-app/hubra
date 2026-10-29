# Finance: payment term and reminders

**Where:** Settings › Module & Plugins › Finance › Einstellungen
(module settings of `finance`).

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `payment_term_days` | int | 30 | Due date of invoices the monthly job generates, and of bulk invoices sent without a date |
| `email_new_invoices` | bool | on | Generated invoices are emailed to the member with the QR-bill |
| `reminders_enabled` | bool | on | The daily reminder job sends reminders (and emits `invoice.overdue`) |
| `first_reminder_days` | int | 7 | Days after the due date for the first reminder |
| `second_reminder_days` | int | 14 | Days after the due date for the second reminder |

The defaults are the values that used to be fixed in the code, so a club
that never opens the form sees no change.

**Rules.** `billing_settings()` in `hubra/api/finance/services.py` reads the
config and keeps it sane: the term and the first reminder are at least one
day, and the second reminder is never earlier than the first. Reminder
history still records the rounds as `overdue_7d` and `overdue_14d`, whatever
the days, so existing history and the "send at most once" check stay valid.

**API.** `POST /finance/invoices/bulk` accepts a body without `due`; the due
date is then today plus the payment term.

**Not included.** Default amount or currency, a third reminder, reminder
fees, and the inventory "block when overdue" rule (still 7 days). Prefilling
the due date in the invoice forms needs the config in the frontend and is a
follow-up.

**Tests:** `tests/finance/test_billing_settings.py`.
