# Backend tests

Tests are organised by **area** (mostly one directory per API blueprint),
with files named by **what they test**, not when they were written.

## Convention

- **Directory** = the area (`auth/`, `finance/`, `members/`, `manager/` for
  the platform API, `tenant/` for the per-club schemas, `plugins/` for the
  plugin loader).
- **File name** = what it covers (`test_login.py`, `test_invoices.py`).
- No sprint, milestone or issue prefixes (`s01_`, `m003_`, `issue022_`).
- A test that spans areas goes in the most relevant directory.
- Shared fixtures for a directory live in its `conftest.py`; the global ones
  (`app`, `client`, `db`, `seeded_db`, `auth_headers`) in the root
  `conftest.py`. Tests that belong to no area (import boundaries, backend
  roles, migrations) sit at the top level.
- `plugins/bundled/` holds small plugins the tests install. The official
  plugins are not tested here: each runs its tests in its own repository
  against Hubra (`plugins/conftest.py`).

## Running

```sh
cd app/backend
python -m pytest -n auto                 # everything, on SQLite
python -m pytest tests/finance/          # one area
python -m pytest tests/auth/test_login.py
```

## Running on Postgres

SQLite enforces no foreign keys here and drops time zones, so some bugs only
show on Postgres. The release checks run the suite on Postgres 18; to do the
same, point `TEST_DATABASE_URL` at a database. With `-n`, each worker gets
its own database next to it (`<name>_gw0`, …, created when missing, so the
role needs `CREATEDB`; see `tests/xdist_postgres.py`):

```sh
TEST_DATABASE_URL=postgresql://hubra:hubra@localhost/hubra_test python -m pytest -n auto
```
