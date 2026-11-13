"""Tests for scripts/release_check.py. Run: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_check as rc

LOG = """# Changelog

Intro text.

## [Unreleased]

### Added

- Something new.

## [1.3.0] - 2026-11-06

### Fixed

- A bug.

## [1.2.0] - 2026-11-01

## [1.1.0] - 2026-10-01

### Added

- Older.
"""


class Repo:
    def __init__(self, version: str, log: str = LOG):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "app/backend").mkdir(parents=True)
        (self.root / rc.PYPROJECT).write_text(f'[project]\nname = "hubra"\nversion = "{version}"\n')
        (self.root / rc.CHANGELOG).write_text(log)


class CheckTest(unittest.TestCase):
    def test_release(self):
        # The bug behind the failed v0.2.3 run: minor read a group of the
        # changelog match instead of the tag match.
        r = Repo("1.3.0")
        self.assertEqual(rc.check("v1.3.0", r.root), {"version": "1.3.0", "prerelease": "false", "minor": "1.3"})

    def test_two_digit_parts(self):
        r = Repo("10.12.3", LOG.replace("[1.3.0]", "[10.12.3]"))
        self.assertEqual(rc.check("v10.12.3", r.root)["minor"], "10.12")

    def test_prerelease_needs_no_section(self):
        r = Repo("1.4.0-rc.1")
        self.assertEqual(rc.check("v1.4.0-rc.1", r.root), {"version": "1.4.0-rc.1", "prerelease": "true", "minor": "1.4"})

    def test_bad_tag(self):
        r = Repo("1.3.0")
        for tag in ("1.3.0", "v1.3", "release-1.3.0", "v1.3.0.1"):
            with self.subTest(tag=tag), self.assertRaisesRegex(rc.ReleaseError, "is not vX.Y.Z"):
                rc.check(tag, r.root)

    def test_version_mismatch(self):
        r = Repo("1.2.9")
        with self.assertRaisesRegex(rc.ReleaseError, "says version 1.2.9"):
            rc.check("v1.3.0", r.root)

    def test_missing_section(self):
        r = Repo("1.5.0")
        with self.assertRaisesRegex(rc.ReleaseError, r"no \[1.5.0\] section"):
            rc.check("v1.5.0", r.root)

    def test_empty_section(self):
        r = Repo("1.2.0")
        with self.assertRaisesRegex(rc.ReleaseError, "is empty"):
            rc.check("v1.2.0", r.root)

    def test_cli_writes_github_output(self):
        r = Repo("1.3.0")
        out = r.root / "out.txt"
        env = {**os.environ, "GITHUB_OUTPUT": str(out)}
        p = subprocess.run([sys.executable, str(Path(rc.__file__)), "check", "v1.3.0", "--root", str(r.root)],
                           env=env, capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(out.read_text(), "version=1.3.0\nprerelease=false\nminor=1.3\n")

    def test_cli_error_exit(self):
        r = Repo("1.5.0")
        p = subprocess.run([sys.executable, str(Path(rc.__file__)), "check", "v1.5.0", "--root", str(r.root)],
                           capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("::error::", p.stderr)


FRAGMENT = "### Added\n\n- From a fragment.\n\n<!-- de -->\n\n### Added\n\n- Aus einem Fragment.\n"


class FragmentRepo(Repo):
    """A Repo with app/backend/changes/ and the real fragment module."""

    def __init__(self, version: str, log: str = LOG):
        super().__init__(version, log)
        real = Path(__file__).resolve().parent.parent / rc.FRAGMENTS
        (self.root / rc.FRAGMENTS).parent.mkdir(parents=True)
        (self.root / rc.FRAGMENTS).write_text(real.read_text())
        (self.root / rc.CHANGES).mkdir()
        (self.root / rc.CHANGES / "README.md").write_text("how to")

    def add(self):
        (self.root / rc.CHANGES / "thing.md").write_text(FRAGMENT)


class FragmentTest(unittest.TestCase):
    def test_fragments_are_fine_between_releases(self):
        r = FragmentRepo("1.3.0")
        r.add()
        self.assertEqual(rc.check("v1.3.0", r.root)["version"], "1.3.0")

    def test_bump_or_tag_refuses_waiting_fragments(self):
        r = FragmentRepo("1.3.0")
        self.assertEqual(rc.check("v1.3.0", r.root, no_fragments=True)["version"], "1.3.0")
        r.add()
        with self.assertRaisesRegex(rc.ReleaseError, "thing.md.*fold"):
            rc.check("v1.3.0", r.root, no_fragments=True)
        env = {**os.environ, "GITHUB_REF_TYPE": "tag", "GITHUB_OUTPUT": ""}
        p = subprocess.run([sys.executable, str(Path(rc.__file__)), "check", "v1.3.0", "--root", str(r.root)],
                           capture_output=True, text=True, check=False, env=env)
        self.assertEqual(p.returncode, 1)
        self.assertIn("fold", p.stderr)

    def test_prerelease_notes_include_fragments(self):
        r = FragmentRepo("1.4.0-rc.1")
        r.add()
        images = r.root / "images.yaml"
        images.write_text("images: []\n")
        text = rc.notes("v1.4.0-rc.1", r.root, images, r.root / "out")
        self.assertIn("- Something new.", text)
        self.assertIn("- From a fragment.", text)
        self.assertNotIn("Aus einem Fragment", text)


class NotesTest(unittest.TestCase):
    def setUp(self):
        self.r = Repo("1.3.0")
        self.images = self.r.root / "images.yaml"
        self.images.write_text("images:\n  - name: ghcr.io/x/backend\n")
        self.out = self.r.root / "out"

    def test_release_notes(self):
        text = rc.notes("v1.3.0", self.r.root, self.images, self.out, repo="hubra-app/hubra")
        self.assertIn("## Changelog\n\n### Fixed\n\n- A bug.", text)
        self.assertNotIn("Older.", text)
        self.assertIn("ghcr.io/x/backend", text)
        self.assertIn("hubra-app/hubra/blob/v1.3.0/docs/releases.md", text)
        self.assertEqual((self.out / "CHANGELOG.md").read_text(), "# Hubra 1.3.0\n\n### Fixed\n\n- A bug.\n")

    def test_draft_body_on_top_without_duplicate(self):
        body = "Highlights.\n\n### Fixed\n\n- A bug."
        text = rc.notes("v1.3.0", self.r.root, self.images, self.out, body=body)
        self.assertTrue(text.startswith("Highlights."))
        self.assertNotIn("## Changelog", text)

    def test_prerelease_uses_unreleased(self):
        text = rc.notes("v1.4.0-rc.1", self.r.root, self.images, self.out)
        self.assertIn("- Something new.", text)

    def test_no_section(self):
        rc.notes("v1.4.0-rc.1", self.r.root, self.images, self.out)
        rc.notes("v9.9.9", self.r.root, self.images, self.out)
        self.assertIn("No changelog entry", (self.out / "CHANGELOG.md").read_text())


class RealChangelogTest(unittest.TestCase):
    """The repository's own files pass the check for the version they declare."""

    def test_current_version(self):
        root = Path(__file__).resolve().parent.parent
        import tomllib
        with open(root / rc.PYPROJECT, "rb") as f:
            version = tomllib.load(f)["project"]["version"]
        self.assertEqual(rc.check(f"v{version}", root)["version"], version)


if __name__ == "__main__":
    unittest.main()


class PluginImpactTest(unittest.TestCase):
    INDEX = {
        "plugins": [
            {"id": "fine", "version": "2.0.0", "hubra": ">=0.2", "versions": []},
            {
                "id": "narrowed",
                "version": "3.0.0",
                "hubra": ">=0.2,<0.3",
                "versions": [{"version": "2.9.0", "hubra": ">=0.2"}],
            },
            {"id": "stuck", "version": "1.0.0", "hubra": ">=0.1,<0.3", "versions": []},
            {"id": "gone", "version": "1.0.0", "yanked": "bad", "versions": []},
            {"id": "open", "version": "0.1.0", "versions": []},
        ]
    }

    def test_ranges(self):
        self.assertTrue(rc.in_range("0.3.0", ">=0.2,<1"))
        self.assertFalse(rc.in_range("1.0.0", ">=0.2,<1"))
        self.assertTrue(rc.in_range("0.2.5", "==0.2.*"))
        self.assertFalse(rc.in_range("0.3.0", "==0.2.*"))
        self.assertTrue(rc.in_range("1.4.0", "~=1.2"))
        self.assertFalse(rc.in_range("2.0.0", "~=1.2"))
        self.assertFalse(rc.in_range("1.3.0", "~=1.2.3"))
        self.assertTrue(rc.in_range("0.3.0", ""))
        with self.assertRaises(rc.ReleaseError):
            rc.in_range("0.3.0", "around 0.3")

    def test_impact_sorts_plugins(self):
        impact = rc.plugin_impact("0.3.0", self.INDEX)
        self.assertEqual([r["id"] for r in impact["ok"]], ["fine", "open"])
        self.assertEqual([(r["id"], r["works"]) for r in impact["update"]], [("narrowed", "2.9.0")])
        self.assertEqual([r["id"] for r in impact["blocked"]], ["stuck"])

    def test_cli_strict_fails_only_on_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            import json

            path.write_text(json.dumps(self.INDEX))
            self.assertEqual(rc.main(["plugins", "v0.2.5", "--index", str(path), "--strict"]), 0)
            self.assertEqual(rc.main(["plugins", "v0.3.0", "--index", str(path)]), 0)
            self.assertEqual(rc.main(["plugins", "v0.3.0", "--index", str(path), "--strict"]), 1)
            self.assertEqual(rc.main(["plugins", "v0.3.0", "--index", str(Path(tmp) / "none.json")]), 0)
