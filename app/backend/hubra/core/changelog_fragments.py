"""Changelog entries that wait for the next release, one file per pull request.

Every pull request used to add its entries under ``## [Unreleased]`` at the
top of CHANGELOG.md and CHANGELOG.de.md, so any two open pull requests
clashed there. Now each adds ``app/backend/changes/<topic>.md`` instead:

    ### Added

    - **Event templates**: ... <!-- for: events -->

    <!-- de -->

    ### Added

    - **Vorlagen für Anlässe**: ... <!-- for: events -->

English first, German after the ``<!-- de -->`` line, with the same sections
and as many items each. The apps show them under [Unreleased]; before a
release, ``python -m hubra.core.changelog_fragments fold`` (or ``python
app/backend/hubra/core/changelog_fragments.py fold`` from the repository)
moves them into the two changelogs and deletes the files. See
app/backend/changes/README.md.

Standard library only: scripts/release_check.py loads this file directly.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
CHANGES = BACKEND / "changes"
CHANGELOGS = {"en": BACKEND / "CHANGELOG.md", "de": BACKEND / "CHANGELOG.de.md"}

GERMAN = re.compile(r"^\s*<!--\s*de\s*-->\s*$", re.M | re.I)
SECTION = re.compile(r"^###\s*(.+?)\s*$")
# Keep a Changelog's order; other sections go after these.
ORDER = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")

Sections = dict[str, list[str]]


class FragmentError(ValueError):
    """A fragment is not in the expected shape; the message names the file."""


def files(changes: Path = CHANGES) -> list[Path]:
    """The fragments, by file name (README.md is not one)."""
    if not changes.is_dir():
        return []
    return sorted(p for p in changes.glob("*.md") if p.name.lower() != "readme.md")


def sections_of(text: str) -> Sections:
    """``### Name`` sections and their items, each item as its raw lines
    (a wrapped item keeps its indented lines)."""
    out: Sections = {}
    current: str | None = None
    for line in text.splitlines():
        m = SECTION.match(line)
        if m:
            current = m.group(1)
            out.setdefault(current, [])
        elif current is not None and line.lstrip().startswith("- ") and not line[:1].isspace():
            out[current].append(line.rstrip())
        elif current is not None and line.strip() and line[:1].isspace() and out[current]:
            out[current][-1] += "\n" + line.rstrip()
    return {k: v for k, v in out.items() if v}


def read(path: Path) -> dict[str, Sections]:
    """One fragment as ``{"en": sections, "de": sections}``."""
    parts = GERMAN.split(path.read_text(encoding="utf-8"))
    if len(parts) != 2:
        raise FragmentError(f"{path.name}: needs one '<!-- de -->' line between English and German")
    en, de = sections_of(parts[0]), sections_of(parts[1])
    if not en:
        raise FragmentError(f"{path.name}: no '### Section' with '- ' items in the English part")
    shape_en = {k: len(v) for k, v in en.items()}
    shape_de = {k: len(v) for k, v in de.items()}
    if shape_en != shape_de:
        raise FragmentError(
            f"{path.name}: German must have the same sections and as many items "
            f"as English ({shape_en} vs {shape_de})"
        )
    return {"en": en, "de": de}


def collected(changes: Path = CHANGES) -> dict[str, Sections]:
    """All fragments merged per language, in file-name order."""
    out: dict[str, Sections] = {"en": {}, "de": {}}
    for path in files(changes):
        for lang, sections in read(path).items():
            for name, items in sections.items():
                out[lang].setdefault(name, []).extend(items)
    return out


def _rank(name: str) -> int:
    return ORDER.index(name) if name in ORDER else len(ORDER)


def fold_into(log: str, sections: Sections) -> str:
    """*log* with *sections* appended to its ``## [Unreleased]`` section
    (created at the top when missing): items go at the end of a section of
    the same name, new sections in Keep a Changelog's order."""
    if not sections:
        return log
    m = re.search(r"^##\s*\[Unreleased\][^\n]*\n", log, re.M | re.I)
    if m is None:
        first = re.search(r"^##\s", log, re.M)
        at = first.start() if first else len(log)
        log = log[:at] + "## [Unreleased]\n\n" + log[at:]
        m = re.search(r"^##\s*\[Unreleased\][^\n]*\n", log, re.M | re.I)
    assert m is not None
    start = m.end()
    nxt = re.search(r"^##\s", log[start:], re.M)
    end = start + nxt.start() if nxt else len(log)
    have = sections_of(log[start:end])
    # Section names in the [Unreleased] body in their order, then new ones.
    names = [n for n in re.findall(r"^###\s*(.+?)\s*$", log[start:end], re.M) if n in have]
    for name in sorted(sections, key=_rank):
        if name not in names:
            later = [i for i, n in enumerate(names) if _rank(n) > _rank(name)]
            names.insert(later[0] if later else len(names), name)
    blocks = []
    for name in names:
        items = have.get(name, []) + sections.get(name, [])
        blocks.append(f"### {name}\n\n" + "\n".join(items) + "\n")
    body = "\n" + "\n".join(blocks) + "\n"
    return log[:start] + body + log[end:].lstrip("\n")


def fold(changes: Path = CHANGES, changelogs: dict[str, Path] = CHANGELOGS) -> list[Path]:
    """Move every fragment into the changelogs and delete it; the files folded."""
    paths = files(changes)
    merged = collected(changes)
    for lang, path in changelogs.items():
        path.write_text(fold_into(path.read_text(encoding="utf-8"), merged[lang]), encoding="utf-8")
    for p in paths:
        p.unlink()
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="read every fragment and report problems")
    sub.add_parser("fold", help="move the fragments into CHANGELOG.md and CHANGELOG.de.md")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "check":
            n = len(files())
            collected()
            print(f"{n} changelog fragment(s) OK")
        else:
            done = fold()
            print(f"folded {len(done)} fragment(s) into CHANGELOG.md and CHANGELOG.de.md")
    except FragmentError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
