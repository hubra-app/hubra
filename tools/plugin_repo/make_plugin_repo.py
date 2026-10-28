#!/usr/bin/env python3
"""Turn a plugin folder into a git repository of its own, the layout of every
official Hubra plugin (hubra-app/hubra-plugin-<id>): the plugin at the root, a
README from its manifest, Hubra's LICENSE, and the workflow that tests it and,
on a GitHub release, signs it and attaches <id>-<version>.zip.

    python3 tools/plugin_repo/make_plugin_repo.py plugins/keys ../hubra-plugin-keys

The Marketplace (hubra-app/hubra-plugins) finds every public hubra-plugin-*
repository of hubra-app by itself.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = HERE / "template"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "dist", "node_modules")


def readme(m: dict, repo: str) -> str:
    return f"""# {m.get("name", m["id"])}

A plugin for [Hubra](https://hubra.club). {m.get("description", "")}

**Version** {m.get("version", "")} · **Works with** Hubra {m.get("hubra") or "any"} · **Plugin id** `{m["id"]}`

## Install

Platform admins install it from the plugin catalogue in the manager portal
(official Marketplace, <https://plugins.hubra.club/index.json>, signed with
the Hubra project key). Clubs then switch it on under Einstellungen → Module
& Plugins.

## Develop

Hubra has this repository as a submodule in `plugins/{m["id"]}`, so its tests
run with Hubra's (`cd app/backend && pytest ../../plugins/{m["id"]}`) and
`npm run build:plugin` in `app/frontend` builds its frontend.

## Releasing

Bump `version` in `plugin.yaml`, add a `## <version>` section to
`CHANGELOG.md`, commit, then publish a GitHub release tagged `v<version>`
(web UI, or `gh release create v<version> --target main --notes ""`). The
workflow tests the plugin, builds its frontend, signs it with the
`HUBRA_SIGNING_KEY` secret and attaches `{m["id"]}-<version>.zip` to the
release. Files listed in `.releaseignore` stay out of the zip.

Source: <https://github.com/hubra-app/{repo}>
"""


def main(src: str, dest: str) -> None:
    s, d = Path(src), Path(dest)
    m = yaml.safe_load((s / "plugin.yaml").read_text())
    d.mkdir(parents=True, exist_ok=True)
    shutil.copytree(s, d, dirs_exist_ok=True, ignore=SKIP)
    (d / "SIGNATURE.json").unlink(missing_ok=True)
    # Its homepage is its own repository now.
    manifest = d / "plugin.yaml"
    text = manifest.read_text()
    home = f"homepage: https://github.com/hubra-app/{d.name}"
    text = re.sub(r"^homepage:.*$", home, text, flags=re.M)
    manifest.write_text(text if home in text else f"{text.rstrip()}\n{home}\n")
    shutil.copytree(TEMPLATE, d, dirs_exist_ok=True)
    if (s / ".releaseignore").is_file():  # the plugin's own list wins
        shutil.copy2(s / ".releaseignore", d / ".releaseignore")
    if not (d / "README.md").exists():
        (d / "README.md").write_text(readme(m, d.name))
    if not (d / "LICENSE").exists() and (ROOT / "LICENSE").is_file():
        shutil.copy2(ROOT / "LICENSE", d / "LICENSE")
    if not (d / "CHANGELOG.md").exists():
        (d / "CHANGELOG.md").write_text(
            f"# {m.get('name', m['id'])}\n\n## {m.get('version', '1.0.0')}\n\nFirst release.\n"
        )
    print(f"{m['id']} {m.get('version')}: {d}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
