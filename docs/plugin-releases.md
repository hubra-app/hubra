# Plugin releases: what to update

Every time an official plugin (`hubra-app/hubra-plugin-<id>`) gets a new
release, or a new plugin repository is added, the places that list the
plugins must be updated in the same go. Nothing does this automatically: the
Marketplace index at plugins.hubra.club updates itself, the pages below do
not.

## Checklist

After the GitHub release `v<version>` is published (not when `plugin.yaml` is
bumped on main, since an unpublished version is not installable):

- [ ] **hubra README** (`README.md`, section *Plugins*): set the version and
      its release link. For a new plugin add a row (name, one-line
      description, version), keeping the table in alphabetical order.
- [ ] **Marketplace README** (`hubra-app/hubra-plugins`, `README.md`): same
      version in the plugin table; for a new plugin add the row.
- [ ] **Modules page** (`hubra-app/hubra.club`, `src/pages/module.html` and
      `src/pages/en/modules.html`): for a new plugin add a card in both
      languages with `data-plugin="<id>"` and a short description; when a
      release changes what a plugin does, update its description. Run
      `python3 tools/build.py` and commit `src/` and `public/` together.
- [ ] **GitHub org profile** (`hubra-app/.github`, `profile/README.md`, the
      page at github.com/hubra-app): set the version in the plugin's row; for
      a new plugin add its row (alphabetical, with description and version).
      Sessions cannot push to `.github`, so this file is edited in the GitHub
      web UI.

Versions are listed in the two READMEs and the org profile; the hubra.club
Modules page shows what each plugin does, and prices come from the public API
at runtime.

## Finding the current versions

The latest GitHub release of each repository is the version to show:

```sh
for r in bank-import budgets codes discord guides imap-inbox inventory keys; do
  gh release view -R hubra-app/hubra-plugin-$r --json tagName -q .tagName
done
```
