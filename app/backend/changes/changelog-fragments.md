### Changed

- **Changelog entries in their own files**: a pull request adds `app/backend/changes/<topic>.md` (English, then German after `<!-- de -->`) instead of editing CHANGELOG.md and CHANGELOG.de.md, so parallel pull requests no longer clash there. The apps show them under [Unreleased]; `changelog_fragments.py fold` moves them into the changelogs before `mason bump`, and the release check refuses a release while any are left. app/backend/changes/README.md. <!-- for: staff -->

<!-- de -->

### Changed

- **Changelog-Einträge in eigenen Dateien**: ein Pull Request legt `app/backend/changes/<Thema>.md` an (Englisch, nach `<!-- de -->` Deutsch), statt CHANGELOG.md und CHANGELOG.de.md zu ändern, damit parallele Pull Requests dort nicht mehr kollidieren. Die Apps zeigen sie unter [Unreleased]; `changelog_fragments.py fold` verschiebt sie vor `mason bump` in die Changelogs, und der Release-Check lehnt ein Release ab, solange noch welche da sind. app/backend/changes/README.md. <!-- for: staff -->
