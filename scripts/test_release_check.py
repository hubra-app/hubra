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
