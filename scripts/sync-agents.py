#!/usr/bin/env python3
"""
Sync agent definitions from .opencode/agent(s)/ files into opencode.json.

Scans both .opencode/agent/ and .opencode/agents/ for agent definition files
(.md, .yaml, .yml, .json), extracts their metadata, and merges the definitions
into the "agent" section of opencode.json.

Usage:
    python scripts/sync-agents.py                  # interactive (asks confirmation)
    python scripts/sync-agents.py --non-interactive # writes without asking
    python scripts/sync-agents.py --dry-run        # show diff only, no write
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr
    )
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENCODE_JSON = REPO_ROOT / "opencode.json"
AGENT_DIRS = [REPO_ROOT / ".opencode" / "agent", REPO_ROOT / ".opencode" / "agents"]
AGENT_EXTENSIONS = {".md", ".yaml", ".yml", ".json"}

BUILTIN_AGENTS = {"plan", "build", "general", "explore"}

# Fields that are valid in the opencode.json agent config.
# "prompt" is excluded because the file body is the source of truth.
SYNCED_FIELDS = {
    "description",
    "mode",
    "model",
    "permission",
    "temperature",
    "top_p",
    "hidden",
    "color",
    "steps",
    "options",
    "tools",  # routed to options by opencode, preserved as-is
    "disable",
    "variant",
}


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n(?:---|\.\.\.)\s*\n", re.DOTALL)


def parse_frontmatter_md(text: str) -> dict:
    """Parse YAML frontmatter from a markdown file. Returns metadata dict."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def parse_yaml_file(text: str) -> dict:
    """Parse a YAML agent definition file."""
    try:
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def parse_json_file(text: str) -> dict:
    """Parse a JSON agent definition file."""
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_agent_file(path: Path) -> dict | None:
    """Parse an agent definition file and return its metadata dict.

    Returns None if the file cannot be parsed or has no useful metadata.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"  WARNING: Cannot read {path}: {exc}", file=sys.stderr)
        return None

    ext = path.suffix.lower()
    if ext == ".md":
        return parse_frontmatter_md(text)
    elif ext in (".yaml", ".yml"):
        return parse_yaml_file(text)
    elif ext == ".json":
        return parse_json_file(text)
    return None


# ---------------------------------------------------------------------------
# Agent scanning
# ---------------------------------------------------------------------------


def scan_agents() -> dict[str, dict]:
    """Scan agent directories and return {name: metadata} for all agents."""
    agents: dict[str, dict] = {}

    for agent_dir in AGENT_DIRS:
        if not agent_dir.is_dir():
            continue
        for path in sorted(agent_dir.iterdir()):
            if path.is_dir():
                continue
            if path.suffix.lower() not in AGENT_EXTENSIONS:
                continue
            if path.name.startswith("."):
                continue

            name = path.stem
            meta = parse_agent_file(path)
            if meta is None:
                continue

            # Strip the "name" field if present in metadata — we use the filename
            meta.pop("name", None)

            # Default mode to "subagent" if not specified
            if "mode" not in meta:
                meta["mode"] = "subagent"

            # Filter to only synced fields
            filtered = {k: v for k, v in meta.items() if k in SYNCED_FIELDS}
            agents[name] = filtered

    return agents


# ---------------------------------------------------------------------------
# opencode.json handling
# ---------------------------------------------------------------------------


def read_opencode_json(path: Path) -> dict:
    """Read and parse opencode.json, preserving key order."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def build_desired_agent_section(
    file_agents: dict[str, dict],
    existing_agents: dict[str, dict],
) -> dict:
    """Build the merged agent section.

    - File-sourced agents are added or updated.
    - Existing agents not in files are preserved (including builtins).
    - Built-in agents are never overwritten with file metadata, but their
      existing overrides (e.g. permission) are preserved.
    """
    merged: dict[str, dict] = {}

    # Start with all existing agents
    for name, config in existing_agents.items():
        merged[name] = dict(config)

    # Add or update from files
    for name, file_meta in file_agents.items():
        if name in merged:
            # Agent exists in config — update from file
            # But skip built-in agents unless the file explicitly defines them
            if name in BUILTIN_AGENTS:
                # For builtins, only merge non-default fields from files
                # This preserves existing permission overrides etc.
                for key, val in file_meta.items():
                    if key == "mode" and val == "subagent":
                        continue  # don't override builtin mode
                    merged[name][key] = val
            else:
                # For custom agents, replace with file definition
                merged[name] = dict(file_meta)
        else:
            # New agent from file
            merged[name] = dict(file_meta)

    return merged


def compute_changes(
    existing_agents: dict[str, dict],
    desired_agents: dict[str, dict],
) -> tuple[list[str], list[str], list[str]]:
    """Compare existing and desired agent sections.

    Returns (added, updated, skipped) lists of agent names.
    """
    added: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for name, desired in desired_agents.items():
        if name not in existing_agents:
            added.append(name)
        elif existing_agents[name] == desired:
            skipped.append(name)
        else:
            updated.append(name)

    return added, updated, skipped


# ---------------------------------------------------------------------------
# Diff and confirmation
# ---------------------------------------------------------------------------


def show_diff(old_config: dict, new_config: dict) -> str:
    """Show a unified diff between old and new opencode.json."""
    old_text = json.dumps(old_config, indent=4, ensure_ascii=False) + "\n"
    new_text = json.dumps(new_config, indent=4, ensure_ascii=False) + "\n"

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="opencode.json (current)",
        tofile="opencode.json (after sync)",
        n=3,
    )
    return "".join(diff)


def confirm(message: str) -> bool:
    """Ask for user confirmation."""
    try:
        answer = input(f"{message} [y/N] ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync agent definitions from files into opencode.json",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Write changes without asking for confirmation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show diff only, do not write",
    )
    args = parser.parse_args()

    # 1. Scan agent files
    file_agents = scan_agents()
    if not file_agents:
        print("No agent definitions found in .opencode/agent/ or .opencode/agents/")
        sys.exit(0)

    print(f"Found {len(file_agents)} agent(s) in definition files:")
    for name in sorted(file_agents):
        mode = file_agents[name].get("mode", "subagent")
        print(f"  - {name} (mode: {mode})")

    # 2. Read current config
    old_config = read_opencode_json(OPENCODE_JSON)
    existing_agents = old_config.get("agent", {})

    # 3. Build merged agent section
    desired_agents = build_desired_agent_section(file_agents, existing_agents)

    # 4. Compute changes
    added, updated, skipped = compute_changes(existing_agents, desired_agents)

    print("\nSummary:")
    print(f"  Added:   {len(added)}")
    print(f"  Updated: {len(updated)}")
    print(f"  Skipped: {len(skipped)} (already in sync)")

    if added:
        print("\n  Agents to add:")
        for name in sorted(added):
            print(f"    + {name}")

    if updated:
        print("\n  Agents to update:")
        for name in sorted(updated):
            print(f"    ~ {name}")

    if not added and not updated:
        print("\nAll agents are already in sync. No changes needed.")
        sys.exit(0)

    # 5. Build new config
    new_config = dict(old_config)
    new_config["agent"] = desired_agents

    # 6. Show diff
    diff = show_diff(old_config, new_config)
    if diff:
        print(f"\n{'=' * 60}")
        print("Diff:")
        print(f"{'=' * 60}")
        print(diff)
    else:
        print("\nNo structural diff (field order may have changed).")

    # 7. Confirm and write
    if args.dry_run:
        print("\n(dry run — no changes written)")
        sys.exit(0)

    if not args.non_interactive:
        if not confirm("\nApply these changes to opencode.json?"):
            print("Aborted.")
            sys.exit(0)

    # Write with consistent formatting
    new_text = json.dumps(new_config, indent=4, ensure_ascii=False) + "\n"
    OPENCODE_JSON.write_text(new_text, encoding="utf-8")
    print(f"\nUpdated {OPENCODE_JSON.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
