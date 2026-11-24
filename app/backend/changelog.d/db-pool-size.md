### Changed

- **Fewer idle database connections**: each backend process (gunicorn worker, Celery child, beat) now keeps at most 2 idle connections open instead of 5, and can still open up to 8 more for a moment when busy (10 at most, was 15). `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` change this. API and worker connections name their process in Postgres (`application_name`, for example `hubra-api`), so `pg_stat_activity` shows which process holds them. docs/scaling.md. <!-- for: staff -->

<!-- de -->

### Changed

- **Weniger offene Datenbankverbindungen**: jeder Backend-Prozess (gunicorn-Worker, Celery-Kind, Beat) hält jetzt höchstens 2 unbenutzte Verbindungen offen statt 5 und kann bei Last kurz bis zu 8 weitere öffnen (höchstens 10, vorher 15). `DB_POOL_SIZE` und `DB_MAX_OVERFLOW` ändern das. API- und Worker-Verbindungen nennen ihren Prozess in Postgres (`application_name`, zum Beispiel `hubra-api`), damit `pg_stat_activity` zeigt, welcher Prozess sie hält. docs/scaling.md. <!-- for: staff -->
