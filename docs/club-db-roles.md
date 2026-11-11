# One database role per club

Every Hubra process (API, worker, beat, Discord gateway) connects to
Postgres as one app role, which can reach every club's schema. Inside a club
the connection also switches to that club's own role (`SET ROLE`), so the
database itself stops a query from touching another club.

Code: `app/backend/hubra/core/tenant/db_roles.py`. Tests:
`app/backend/tests/tenant/test_db_roles.py` (Postgres only).

## What a club role may do

| Where | Rights |
|-------|--------|
| its own schema `tenant_<id>` | everything on its tables and sequences, `CREATE` on the schema |
| shared tables in public (users, tenants, settings, ...) | `SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER` through the group role `<database>_clubs` |
| template copies of the club tables in public | nothing |
| other clubs' schemas | nothing |

So a query that names another club's schema, or a club table missing from
the club's schema (which used to fall through to the empty template in
public), fails with `permission denied`.

Roles are named `<database>_club_<id>`. Role names are global to the
Postgres server, so the database name keeps two Hubra databases on one
server apart.

## When the role is used

- A request in a club (the tenant middleware), a background job queued for a
  club (`tenant_id` header), `in_club(...)` and per-club scheduled jobs all go
  through `set_search_path(tenant_id)`, which also sets the club's role.
- Leaving the club (`reset_search_path`) and migrations
  (`set_search_path(..., as_club=False)`, plugin migrations) run as the app
  role.
- A pooled connection drops its club role when it goes back to the pool, so
  the next user starts as the app role.

## Lifecycle

- A new club gets its role when its schema is created.
- `flask sync-tenant-schemas` (the init step, on every start) creates the
  roles of existing clubs, grants new shared tables and takes the rights on
  new template tables away again. Plugin installs and updates do the same.
- A club backup restore gives the restored schema back to the club's role.
- Deleting a club's schema drops its role.

## Requirements

The app role needs `CREATEROLE` (or is the superuser, as on old Compose
stacks). On PostgreSQL 16 and later a `CREATEROLE` role can only manage the
roles it created itself. Without it nothing changes: no roles are made, no
`SET ROLE` is sent, and the init step prints "Club database roles: off".

## What it does not do

The connection still logs in as the app role. SQL that runs `RESET ROLE`
gets the app role's rights back, so this guards against mistakes (a wrong
search path, a schema-qualified query, a missing table), not against code
written to break out. That is why plugins are signed. Shared tables in
public that hold rows of several clubs (for example `user_tenants`) stay
readable by every club role; their queries still filter by club.
