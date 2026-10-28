# Test Directory Structure

Tests are organized by **API blueprint** (one directory per blueprint), with
files named by **what they test**, not when they were written.

## Convention

- **Directory** = blueprint name (e.g. `auth/`, `finance/`, `members/`)
- **File name** = functional area within that blueprint (e.g. `test_login.py`,
  `test_invoices.py`, `test_crud.py`)
- No sprint/milestone/issue prefixes (`s01_`, `m003_`, `issue022_` etc.)
- Cross-cutting concerns go to the most relevant blueprint directory
  (e.g. lifecycle tests that span applications + members go to `applications/`)
- Shared fixtures for a directory live in that directory's `conftest.py`
- Global fixtures (`app`, `client`, `db`, `seeded_db`, `auth_headers`) live in
  the root `conftest.py`

## Directories

| Directory         | Blueprint               | Files                                        |
|-------------------|-------------------------|----------------------------------------------|
| `account/`        | account_bp              | `test_account_api.py`                        |
| `applications/`   | applications_bp         | `test_approve_lifecycle.py`                  |
| `audit/`          | audit_bp                | `test_audit_log.py`                          |
| `auth/`           | auth_bp                 | `test_login.py`, `test_account.py`,          |
|                   |                         | `test_lockout.py`, `test_password_reset.py`  |
|                   |                         | `test_bootstrap.py`, `test_rate_limiting.py` |
|                   |                         | `test_refresh_lockout.py`                    |
| `finance/`        | finance_bp              | `test_transactions.py`, `test_invoices.py`   |
|                   |                         | `test_invoice_tasks.py`,                     |
|                   |                         | `test_invoice_linkage.py`                    |
| `functions/`      | functions_bp            | `test_functions.py`                          |
| `groups/`         | groups_bp               | `test_delete.py`, `test_membership_hooks.py` |
| `health/`         | health_bp               | `test_health.py`                             |
| `inventory/`      | inventory_bp            | `test_inventory.py`                          |
| `mail/`           | mail_bp                 | `test_wildduck.py`, `test_email_service.py`  |
|                   |                         | `test_group_mail.py`, `test_member_mail.py`  |
|                   |                         | `test_mail_tasks.py`                         |
| `members/`        | members_bp              | `test_crud.py`, `test_set_password.py`,      |
|                   |                         | `test_disable_enable.py`,                    |
|                   |                         | `test_member_mail.py`                        |
| `polls/`          | polls_bp                | `test_polls.py`                              |
| `roles/`          | roles_bp                | `test_roles.py`, `test_role_permissions.py`  |
| `settings/`       | settings_bp             | `test_settings_kv.py`                        |
| `system/`         | system_bp               | `test_permissions.py`, `test_foundation.py`  |
|                   |                         | `test_security_headers.py`,                  |
|                   |                         | `test_subdomain_cors.py`                     |

## Running Tests

```sh
# All tests (756 passed)
python -m pytest tests/ --ignore=tests/test_s11_backend_gaps.py

# Specific blueprint
python -m pytest tests/finance/

# Specific file
python -m pytest tests/auth/test_login.py

# With coverage
python -m pytest tests/ --ignore=tests/test_s11_backend_gaps.py --cov=hubra
```

> `test_s11_backend_gaps.py` requires a running Redis instance and will hang
> if Redis is unavailable. Always use `--ignore=tests/test_s11_backend_gaps.py`
> when testing without Docker.

## Running on Postgres

The suite uses in-memory SQLite by default. SQLite enforces no foreign keys
here and drops time zones, so some bugs only show on Postgres. Point
`TEST_DATABASE_URL` at an empty database the tests may wipe:

```bash
createdb hubra_test
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1/hubra_test pytest -q \
  --ignore=tests/auth/test_rate_limiting.py --ignore=tests/mail/test_email_service.py
```

The two ignored files build their own app on the same database, which only
works with SQLite's per-app in-memory database. This runs every table in one
schema; it does not test the per-club schemas.
