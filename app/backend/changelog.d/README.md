# Changelog entries waiting for the next release

Add one file here per pull request instead of editing `CHANGELOG.md` and
`CHANGELOG.de.md`. Two pull requests that both edit `## [Unreleased]` always
clash; two new files never do.

Name it after your change, for example `event-templates.md`. Same rules as
the changelog (AGENTS.md, CONTRIBUTING.md): English first, then the
`<!-- de -->` line, then the same sections with as many items in German
(Swiss spelling, no ß). The section headings stay English.

```markdown
### Added

- **Event templates**: save an event as a template and start new ones from it. <!-- for: events -->

<!-- de -->

### Added

- **Vorlagen für Anlässe**: einen Anlass als Vorlage speichern und neue daraus anlegen. <!-- for: events -->
```

The apps show these entries under [Unreleased] like the ones in the
changelog, and `tests/test_changelog_fragments.py` checks their shape.

## At a release

Before `mason bump`, move them into the changelogs:

```sh
python3 app/backend/hubra/core/changelog_fragments.py fold
```

That appends every entry to `## [Unreleased]` in both files (in file-name
order) and deletes the fragments; `mason bump` then turns [Unreleased] into
the new version. The release check refuses a version while fragments are
still here.
