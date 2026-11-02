# Early access: new features club by club

Every club runs the same Hubra build. To show a new feature to a few clubs
first (a "canary" group) and to everybody later, put it behind a flag.

## Stages

Each flag has one stage. Platform admins set it in
**manage › Plattform-Einstellungen › Früher Zugang**:

| Stage | Who gets the feature |
|---|---|
| `off` (Aus) | nobody |
| `early` (Testgruppe) | the clubs in the early-access group |
| `all` (Alle Vereine) | every club |

To put a club in the early-access group, open it in **Alle Vereine** and use the
**Früher Zugang** card. You can also force a feature always on or always off
for one club, whatever its stage. That is useful for a club that reported a
problem, or that asked for a feature early.

Stage changes and club changes go to the platform audit log
(`platform.feature.stage`, `tenant.early_access`).

## Adding a flag

1. Add the flag to `FLAGS` in `app/backend/hubra/core/services/feature_flags.py`:

   ```python
   FLAGS: dict[str, Flag] = {
       "new_calendar": Flag(
           "new_calendar",
           "Neuer Kalender",
           "New calendar",
           "Monats- und Wochenansicht für Anlässe und Trainings.",
           "Month and week view for events and trainings.",
       ),
   }
   ```

   `default` is the stage until someone sets one in manage (`"off"` unless given).

2. Gate the code.

   Backend, for the club of the request:

   ```python
   from hubra.core.services.feature_flags import is_on, require_feature

   if is_on("new_calendar"):
       ...

   @bp.get("/calendar")
   @require_feature("new_calendar")   # 404 while it is off for the club
   def calendar(): ...
   ```

   Club app:

   ```tsx
   import { useFeature } from '@/api/features'

   const newCalendar = useFeature('new_calendar') // false while loading
   ```

   The club app reads every flag for its club from `GET /api/v1/features`.

3. Release, set the stage to **Testgruppe**, and check the feature with those clubs.
   Then set it to **Alle Vereine**.

4. Once it has been on for everybody for a release, remove the flag and the
   checks from the code. A stage stored for a flag the code no longer knows is
   ignored.

## What a flag is not

A flag switches code paths, not database schemas. Migrations still run for
every club at once, so a gated feature's tables and columns must be safe to
exist while the feature is off.
