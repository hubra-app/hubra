# Database migrations

Migrations live in `app/backend/migrations/versions/` (Alembic through Flask-Migrate).
Make them with `flask db migrate -m "..."`; see AGENTS.md for when a hand-written one is fine.

## Several heads are fine

Several pull requests are often open at once, and each adds its migration on the head it saw.
Once two of them are merged, main has two heads. That is allowed, so nobody has to add a merge
migration to a pull request just because main moved:

- `flask db upgrade` applies every head (Hubra sets its default to `heads`; Compose runs
  `flask db upgrade heads`). The post-deploy step, `flask seed` and new clubs' schemas do the same.
- `flask db migrate` and `flask db revision` base a new migration on every head (default `heads`),
  so it joins them by itself.
- The backend waits until every head of its image is applied (`hubra.core.schema_wait`).

If you call Alembic yourself, say `heads`: `flask db upgrade head` fails while there are several.

## Unjoined heads must change different tables

Alembic picks the order of migrations on different branches. `tests/test_migrations_heads.py`
fails when two unjoined branches change the same table (`op.create_table`, `add_column`,
`batch_alter_table`, `create_index` and so on; SQL in `op.execute` is not read). Then let the
later migration follow the other one (set its `down_revision` to that revision) or add a merge
migration with `flask db merge heads`.

## Tidying up

Heads may pile up between releases. A release may join them with `flask db merge heads -m "join
heads"`; that changes nothing in the database.
