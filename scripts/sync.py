#!/usr/bin/env python3
"""
Sync work items and milestones between local Markdown files and GitLab.

Push direction (local → GitLab):
    - Create/update issues from docs/workitems/*.md files
    - Sync labels (Priority, Status, type) on each issue
    - Create/update milestones from docs/milestones/*.md
    - Attach issues to milestones based on milestone item references

Pull direction (GitLab → local):
    - Create local .md files for GitLab issues that have no local counterpart
    - Create local .md files for GitLab milestones that have no local counterpart
    - Update existing local files when GitLab content diverges

Required environment variables:
    GITLAB_TOKEN    Personal access token with `api` scope
    GITLAB_PROJECT  Project namespace/path or numeric ID  (e.g. mygroup/myrepo)

Optional:
    GITLAB_URL      GitLab base URL  (default: https://gitlab.com)
    DRY_RUN         Set to "1" to skip all writes (default: 0)

Usage:
    GITLAB_TOKEN=... GITLAB_PROJECT=mygroup/myrepo python scripts/sync_issues.py

Dry-run:
    DRY_RUN=1 GITLAB_TOKEN=... GITLAB_PROJECT=... python scripts/sync_issues.py
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
import dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKITEMS_DIR = REPO_ROOT / "docs" / "workitems"
MILESTONES_DIR = REPO_ROOT / "docs" / "milestones"
ARCHIVE_DIR = REPO_ROOT / "docs" / "archive"
MAP_FILE = REPO_ROOT / ".gitlab-map.json"
MILESTONE_MAP_FILE = REPO_ROOT / ".gitlab-milestones.json"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def parse_section(text: str, heading: str) -> str:
    """Return the content under a ## heading, stripped."""
    pattern = rf"^## {re.escape(heading)}\s*\n([\s\S]*?)(?=^## |\Z)"
    m = re.search(pattern, text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def slugify(title: str) -> str:
    """Convert a title to a filesystem-safe slug."""
    s = title.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def work_item_id(path: Path) -> str | None:
    """Extract the item ID (e.g. ISSUE-090, FEATURE-001, QUESTION-001) from H1."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^# (ISSUE|FEATURE|QUESTION)-(\d+)", text, re.MULTILINE)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def work_item_type(item_id: str) -> str:
    return item_id.split("-")[0].lower()


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n(?:---|\.\.\.)\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-like --- frontmatter. Returns (meta, body)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip().lower()] = val.strip()
    return meta, text[m.end() :]


FRONTMATTER_KEYS = ["id", "status", "priority", "type", "milestone"]


def render_frontmatter(meta: dict) -> str:
    """Render metadata dict as frontmatter string."""
    lines = ["---"]
    for key in FRONTMATTER_KEYS:
        val = meta.get(key)
        if val:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def update_frontmatter(text: str, meta: dict) -> str:
    """Add or merge frontmatter into markdown text."""
    existing, body = parse_frontmatter(text)
    existing.update(meta)
    return render_frontmatter(existing) + body.lstrip()


# ---------------------------------------------------------------------------
# Work item parsing
# ---------------------------------------------------------------------------


def parse_work_item(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    effective = body or text

    wid = meta.get("id") or work_item_id(path) or path.stem

    # H1: may be "# ISSUE-090 - Title" or "# Title"
    title_m = re.search(r"^# (.+)$", effective, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else path.stem
    title = re.sub(r"^(ISSUE|FEATURE|QUESTION)-\d+\s*[-–—]\s*", "", title).strip()

    # Frontmatter values take priority; fall back to ## sections
    status = meta.get("status", parse_section(effective, "Status")).lower()
    priority = meta.get("priority", parse_section(effective, "Priority"))
    milestone = meta.get("milestone", "")

    gl_state = "closed" if status in ("closed", "resolved", "fixed") else "opened"

    return {
        "file": path.name,
        "id": wid,
        "item_type": work_item_type(wid),
        "title": title,
        "full_title": title_m.group(1).strip() if title_m else path.stem,
        "description": effective.strip(),
        "state": gl_state,
        "status": status,
        "priority": priority,
        "milestone": milestone,
        "_meta": meta,
        "_body": effective,
    }


def scan_work_items() -> list[dict]:
    """Scan docs/workitems/ for all .md files and return parsed items.

    If multiple files have the same work-item ID (e.g. ISSUE-002 in H1),
    only the file whose filename number matches the ID number is kept.
    """
    raw: list[dict] = []
    for pattern in ("issue-*.md", "feature-*.md", "question-*.md"):
        for path in sorted(WORKITEMS_DIR.glob(pattern)):
            raw.append(parse_work_item(path))

    # Deduplicate by work-item ID
    seen: dict[str, dict] = {}
    for item in raw:
        wid = item["id"]
        if wid not in seen:
            seen[wid] = item
            continue

        existing = seen[wid]
        # Prefer the file whose number matches the ID
        num_in_filename = re.match(r"^(?:issue|feature|question)-(\d+)", item["file"])
        num_in_existing = re.match(
            r"^(?:issue|feature|question)-(\d+)", existing["file"]
        )
        item_matches = num_in_filename and num_in_filename.group(1) == wid.split("-")[1]
        existing_matches = (
            num_in_existing and num_in_existing.group(1) == wid.split("-")[1]
        )

        if item_matches and not existing_matches:
            print(f"  DEDUP  replace {existing['file']} with {item['file']} (ID {wid})")
            seen[wid] = item
        elif not item_matches and existing_matches:
            print(
                f"  DEDUP  skip {item['file']} (ID {wid} already mapped to {existing['file']})"
            )
        else:
            print(
                f"  DEDUP  skip {item['file']} (ID {wid} conflict with {existing['file']})"
            )

    return list(seen.values())


def build_id_index(items: list[dict]) -> dict[str, dict]:
    """Return { 'ISSUE-090': <item>, 'FEATURE-001': <item>, ... }"""
    return {it["id"]: it for it in items if it["id"]}


# ---------------------------------------------------------------------------
# Milestone parsing
# ---------------------------------------------------------------------------


def parse_milestone(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    mid_m = re.search(r"^# (M\d+)", text)
    mid = mid_m.group(1) if mid_m else path.stem

    title_m = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else path.stem

    theme_m = re.search(r"\*\*Theme:\*\*\s*(.*)", text)
    theme = theme_m.group(1).strip() if theme_m else ""

    target_m = re.search(r"\*\*Target:\*\*\s*(.*)", text)
    target = target_m.group(1).strip() if target_m else ""

    # Extract item IDs from the Items table
    item_ids: list[str] = []
    in_items = False
    for line in text.splitlines():
        if line.strip().startswith("| ID "):
            in_items = True
            continue
        if line.strip().startswith("| ---"):
            continue
        if in_items:
            if line.strip().startswith("|"):
                m = re.match(r"\|\s*((?:ISSUE|FEATURE|QUESTION)-\d+)", line)
                if m:
                    item_ids.append(m.group(1).strip())
            elif not line.strip().startswith("|"):
                in_items = False

    dod = parse_section(text, "Definition of Done")

    return {
        "file": path.name,
        "id": mid,
        "title": title,
        "theme": theme,
        "target": target,
        "item_ids": item_ids,
        "content": text.strip(),
        "dod": dod,
    }


def scan_milestones() -> list[dict]:
    return sorted(
        [parse_milestone(p) for p in MILESTONES_DIR.glob("M*.md")],
        key=lambda m: m["id"],
    )


def build_milestone_index(milestones: list[dict]) -> dict[str, dict]:
    """Return { 'M006': <milestone>, ... }"""
    return {m["id"]: m for m in milestones}


# ---------------------------------------------------------------------------
# Map file helpers
# ---------------------------------------------------------------------------


def load_map(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_map(path: Path, mapping: dict) -> None:
    path.write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Map value helpers (migration from old flat format to {iid, state} objects)
# ---------------------------------------------------------------------------


def map_entry(iid: int, state: str | None = None, milestone: str | None = None) -> dict:
    """Create a map value."""
    e: dict = {"iid": iid}
    if state:
        e["state"] = state
    if milestone:
        e["milestone"] = milestone
    return e


def map_get_iid(val) -> int:
    """Extract IID from a map entry, tolerating old bare-int format."""
    return int(val["iid"]) if isinstance(val, dict) else int(val)


def map_get_state(val) -> str | None:
    """Extract optional state from a map entry."""
    return val.get("state") if isinstance(val, dict) else None


def map_get_milestone(val) -> str | None:
    """Extract optional milestone local ID from a map entry."""
    return val.get("milestone") if isinstance(val, dict) else None


def map_ensure_migrated(mapping: dict) -> None:
    """Upgrade old-format map values ({fn: int}) to new format ({fn: {iid, state}})."""
    for key in list(mapping.keys()):
        val = mapping[key]
        if not isinstance(val, dict):
            # Also capture state from the key itself (legacy archives)
            mapping[key] = {"iid": int(val)}
    # Remove entries with null/None iid
    for key in list(mapping.keys()):
        if mapping[key] is None or (
            isinstance(mapping[key], dict) and mapping[key].get("iid") is None
        ):
            del mapping[key]


def build_reverse_index(issue_map: dict) -> dict[int, str]:
    """Return {iid: filename} from the map.

    Detects and prints duplicates — if multiple files claim the same IID,
    the first encountered wins and warnings are emitted.
    """
    rev: dict[int, str] = {}
    for fname, val in issue_map.items():
        iid = map_get_iid(val)
        if iid in rev:
            print(f"  WARNING: Duplicate IID #{iid} — {rev[iid]} and {fname}")
        else:
            rev[iid] = fname
    return rev


# ---------------------------------------------------------------------------
# GitLab client
# ---------------------------------------------------------------------------


class GitLabClient:
    def __init__(self, base_url: str, token: str, project: str):
        encoded = requests.utils.quote(str(project), safe="")  # type: ignore
        base = f"{base_url.rstrip('/')}/api/v4/projects/{encoded}"
        self.project_url = base
        self.issues_url = f"{base}/issues"
        self.milestones_url = f"{base}/milestones"
        self.labels_url = f"{base}/labels"
        self.session = requests.Session()
        self.session.headers["PRIVATE-TOKEN"] = token

    # -- Pagination helper --

    def _get_all(self, url: str, params: dict | None = None) -> list[dict]:
        results = []
        page = 1
        while True:
            p = {"page": page, "per_page": 100, **(params or {})}
            resp = self.session.get(url, params=p)
            resp.raise_for_status()
            results.extend(resp.json())
            if "next" not in resp.links:
                break
            page += 1
        return results

    # -- Issues --

    def create_issue(
        self, title: str, description: str, state: str, labels: list[str] | None = None
    ) -> dict:
        payload: dict = {"title": title, "description": description}
        if state == "closed":
            payload["state_event"] = "close"
        if labels:
            payload["labels"] = ",".join(labels)
        resp = self.session.post(self.issues_url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def update_issue(
        self,
        iid: int,
        title: str,
        description: str,
        state: str,
        labels: list[str] | None = None,
        milestone_id: int | None = None,
    ) -> dict:
        payload: dict = {"title": title, "description": description}
        if state == "closed":
            payload["state_event"] = "close"
        else:
            payload["state_event"] = "reopen"
        if labels is not None:
            payload["labels"] = ",".join(labels)
        if milestone_id is not None:
            payload["milestone_id"] = milestone_id
        resp = self.session.put(f"{self.issues_url}/{iid}", json=payload)
        resp.raise_for_status()
        return resp.json()

    def fetch_all_issues(self, state: str = "all") -> list[dict]:
        return self._get_all(self.issues_url, {"state": state, "scope": "all"})

    def get_issue(self, iid: int) -> dict:
        resp = self.session.get(f"{self.issues_url}/{iid}")
        resp.raise_for_status()
        return resp.json()

    # -- Milestones --

    def create_milestone(self, title: str, description: str) -> dict:
        resp = self.session.post(
            self.milestones_url,
            json={"title": title, "description": description},
        )
        resp.raise_for_status()
        return resp.json()

    def update_milestone(
        self, milestone_iid: int, title: str, description: str
    ) -> dict:
        resp = self.session.put(
            f"{self.milestones_url}/{milestone_iid}",
            json={"title": title, "description": description},
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_all_milestones(self) -> list[dict]:
        return self._get_all(self.milestones_url)

    # -- Labels --

    def ensure_label(self, name: str, color: str, description: str = "") -> None:
        """Create or update a label. Idempotent."""
        payload = {
            "name": name,
            "color": color,
            "description": description,
        }
        resp = self.session.post(self.labels_url, json=payload)
        if resp.status_code == 409:
            # Label already exists — update it
            encoded = requests.utils.quote(name, safe="")
            self.session.put(f"{self.labels_url}/{encoded}", json=payload)
        else:
            resp.raise_for_status()

    def ensure_labels(self, labels: list[dict]) -> None:
        for lbl in labels:
            self.ensure_label(**lbl)


# ---------------------------------------------------------------------------
# Label definitions
# ---------------------------------------------------------------------------

STATUS_LABELS = {
    "open": ("status::open", "#1baaaa"),
    "closed": ("status::closed", "#7758a3"),
    "resolved": ("status::resolved", "#228B22"),
    "fixed": ("status::fixed", "#228B22"),
    "in progress": ("status::in progress", "#FF8C00"),
}

PRIORITY_LABELS = {
    "critical": ("priority::critical", "#8B0000"),
    "high": ("priority::high", "#FF4500"),
    "medium": ("priority::medium", "#FFD700"),
    "low": ("priority::low", "#708090"),
}

TYPE_LABELS = {
    "issue": ("type::issue", "#428bca"),
    "feature": ("type::feature", "#5cb85c"),
    "question": ("type::question", "#f0ad4e"),
}


def build_labels(item: dict) -> list[str]:
    """Return list of label name strings for a work item."""
    labels = []
    raw_status = item.get("status", "open").lower().strip()
    raw_priority = item.get("priority", "medium").lower().strip()
    itype = item.get("item_type", "issue")

    for key, (lbl, _color) in STATUS_LABELS.items():
        if raw_status.startswith(key):
            labels.append(lbl)
            break
    else:
        labels.append("status::open")

    for key, (lbl, _color) in PRIORITY_LABELS.items():
        if raw_priority == key:
            labels.append(lbl)
            break

    for key, (lbl, _color) in TYPE_LABELS.items():
        if itype == key:
            labels.append(lbl)
            break

    return labels


def all_label_defs() -> list[dict]:
    """Return all label definitions for ensure_labels()."""
    defs = []
    for _k, (name, color) in STATUS_LABELS.items():
        defs.append({"name": name, "color": color, "description": "Issue status"})
    for _k, (name, color) in PRIORITY_LABELS.items():
        defs.append({"name": name, "color": color, "description": "Issue priority"})
    for _k, (name, color) in TYPE_LABELS.items():
        defs.append({"name": name, "color": color, "description": "Work item type"})
    return defs


def lookup_filename_by_iid(issue_map: dict, iid: int) -> str | None:
    """Return the filename in the map that corresponds to a GitLab IID."""
    for fname, v in issue_map.items():
        if map_get_iid(v) == iid:
            return fname
    return None


def ensure_filename_matches_iid(
    item: dict, iid: int, issue_map: dict, dry_run: bool
) -> str | None:
    """If the local file's number doesn't match the GitLab IID, rename it.

    Also updates the H1 inside the file (ISSUE-002 → ISSUE-008).
    Returns the *new* filename, or None if no rename was needed.
    """
    itype = item["item_type"]
    slug = slugify(item["title"])
    expected = f"{itype}-{iid:03d}-{slug}.md"
    current = item["file"]

    if current == expected:
        return None  # already correct

    # Check if another file already claims this IID
    existing = lookup_filename_by_iid(issue_map, iid)
    if existing and existing != current:
        print(f"  CONFLICT: {current} wants IID #{iid} but {existing} already has it")
        return None

    src = WORKITEMS_DIR / current
    dst = WORKITEMS_DIR / expected

    if not src.exists():
        return None

    if dst.exists() and not dry_run:
        print(f"  SKIP RENAME: {expected} already exists")
        return None

    print(f"  RENAME  {current} → {expected}")

    if not dry_run:
        # Update H1 and frontmatter ID in the file content
        old_h1 = item["full_title"]
        prefix = itype.upper()
        new_h1 = re.sub(
            rf"^{prefix}-\d+",
            f"{prefix}-{iid:03d}",
            old_h1,
        )
        text = src.read_text(encoding="utf-8")
        # Replace H1
        text = text.replace(old_h1, new_h1, 1)
        # Update frontmatter id field
        meta, body = parse_frontmatter(text)
        if meta:
            meta["id"] = f"{prefix}-{iid:03d}"
            text = render_frontmatter(meta) + body.lstrip()
        dst.write_text(text, encoding="utf-8")
        src.unlink()

        # Update map
        entry = issue_map.get(current, {})
        entry_state = (
            map_get_state(entry) if isinstance(entry, dict) else item.get("state")
        )
        entry_ms = (
            map_get_milestone(entry)
            if isinstance(entry, dict)
            else item.get("milestone")
        )
        del issue_map[current]
        issue_map[expected] = map_entry(
            iid, entry_state or item.get("state"), entry_ms or item.get("milestone")
        )

    return expected


def build_milestone_reverse(milestone_map: dict) -> dict[int, str]:
    """Return {gl_iid: local_milestone_id} from milestone_map."""
    rev: dict[int, str] = {}
    for local_id, val in milestone_map.items():
        iid = map_get_iid(val)
        rev[iid] = local_id
    return rev


DUPLICATE_PATTERN = re.compile(r"^(issue|feature|question)-(\d+)-\1-(\d+)-.+\.md$")


def cleanup_pull_duplicates(issue_map: dict, dry_run: bool) -> bool:
    """Remove corrupted files produced by earlier buggy pull logic.

    Pattern: {type}-{NNN}-{type}-{YYY}-*.md  (e.g. issue-008-issue-002-*.md)
    These were created when make_work_item_file() did not strip the leading
    ISSUE/ FEATURE / QUESTION prefix from GitLab issue titles.

    If the original file ({type}-{YYY}-*.md) still exists, the duplicate is
    deleted outright.  Otherwise the duplicate is the only copy — we fix
    its filename and content.
    """
    changed = False
    for fname in list(issue_map.keys()):
        m = DUPLICATE_PATTERN.match(fname)
        if not m:
            continue
        itype, new_num_str, old_num_str = m.group(1), m.group(2), m.group(3)
        old_num = int(old_num_str)

        path = WORKITEMS_DIR / fname
        if not path.exists():
            # Already removed — clean up the map entry
            print(f"  CLEANUP  {fname}  (orphaned map entry — file missing)")
            if not dry_run:
                del issue_map[fname]
                changed = True
            continue

        # Look for the original file (wildcard slug)
        originals = sorted(WORKITEMS_DIR.glob(f"{itype}-{old_num:03d}-*.md"))
        originals = [p for p in originals if not DUPLICATE_PATTERN.match(p.name)]

        if originals:
            # Original exists — safe to delete the duplicate
            print(f"  CLEANUP  {fname}  (duplicate, original: {originals[0].name})")
            if not dry_run:
                path.unlink()
                del issue_map[fname]
                changed = True
        else:
            # Duplicate IS the only copy — rename to correct filename
            text = path.read_text(encoding="utf-8")
            h1_m = re.search(r"^# (.+)$", text, re.MULTILINE)
            if not h1_m:
                continue
            raw_h1 = h1_m.group(1).strip()
            # The H1 looks like "ISSUE-008 - ISSUE-002 - Something"
            # Strip the double prefix
            fixed_title = re.sub(
                r"^(ISSUE|FEATURE|QUESTION)-\d+\s*[-–—]\s*"
                r"(?:ISSUE|FEATURE|QUESTION)-\d+\s*[-–—]\s*",
                "",
                raw_h1,
            ).strip()
            if not fixed_title:
                continue
            slug = slugify(fixed_title)
            new_fname = f"{itype}-{new_num_str}-{slug}.md"
            new_path = WORKITEMS_DIR / new_fname
            if new_path.exists():
                print(f"  SKIP  {fname}: target {new_fname} already exists")
                continue
            print(f"  REPAIR  {fname} → {new_fname}")
            if not dry_run:
                fixed_h1 = f"{itype.upper()}-{new_num_str} - {fixed_title}"
                text = text.replace(raw_h1, fixed_h1, 1)
                new_path.write_text(text, encoding="utf-8")
                path.unlink()
                del issue_map[fname]
                issue_map[new_fname] = map_entry(int(new_num_str))
                changed = True

    return changed


# ---------------------------------------------------------------------------
# Pull: GitLab → Local Markdown
# ---------------------------------------------------------------------------


def make_work_item_file(
    gl_issue: dict, iid: int, milestone_local_id: str | None = None
) -> str:
    """Generate a local .md file from a GitLab issue dict."""
    raw_title = gl_issue["title"]
    clean_title = re.sub(
        r"^(ISSUE|FEATURE|QUESTION)-\d+\s*[-–—]\s*",
        "",
        raw_title,
    ).strip()

    desc = gl_issue.get("description") or ""
    state = gl_issue["state"]
    gl_labels = gl_issue.get("labels", [])

    priority = "Medium"
    item_type = "issue"
    for lbl in gl_labels:
        if lbl.startswith("priority::"):
            priority = lbl.split("::", 1)[1].capitalize()
        if lbl.startswith("type::"):
            t = lbl.split("::", 1)[1]
            if t in ("issue", "feature", "question"):
                item_type = t

    prefix = item_type.upper()
    item_id = f"{prefix}-{iid:03d}"

    # Build frontmatter
    fm = {
        "id": item_id,
        "status": state.capitalize(),
        "priority": priority,
        "type": item_type,
    }
    if milestone_local_id:
        fm["milestone"] = milestone_local_id

    lines = [
        render_frontmatter(fm).rstrip(),
        "",
        f"# {item_id} - {clean_title}",
        "",
    ]
    if item_type in ("issue", "question"):
        lines.extend(["## Resolution", "", "Not Resolved", ""])
    lines.extend(["## Fixed (Date)", "", "N/A", ""])

    section_heading = {
        "issue": "## Issue",
        "feature": "## Feature",
        "question": "## Question",
    }.get(item_type, "## Description")
    lines.extend(["", section_heading, "", desc, ""])
    lines.extend(["", "## Scope", "", "", "## Acceptance Criteria", "", ""])

    return "\n".join(lines)


def make_milestone_file(gl_milestone: dict) -> str:
    """Generate a local milestone .md from a GitLab milestone dict."""
    title = gl_milestone["title"]
    desc = gl_milestone.get("description") or ""
    # Extract the Mxxx ID from the title if present
    mid_m = re.search(r"(M\d+)", title)
    mid = mid_m.group(1) if mid_m else title

    lines = [
        f"# {mid} - {title}",
        "",
        "**Theme:** (auto-imported from GitLab)",
        "",
        "**Target:** (auto-imported from GitLab)",
        "",
        "## Items",
        "",
        "| ID | Title | Priority |",
        "|---|---|---|",
        "",
        "## Dependencies",
        "",
        "## Definition of Done",
        "",
        desc,
        "",
    ]
    return "\n".join(lines)


def pull_issues(
    client: GitLabClient, issue_map: dict, milestone_map: dict, dry_run: bool
) -> list[dict]:
    """Fetch all GitLab issues and create/update local files for unknowns."""
    gl_issues = client.fetch_all_issues(state="all")
    pulled: list[dict] = []
    ms_rev = build_milestone_reverse(milestone_map)

    # Build reverse index and known-filename set
    known_fnames: set[str] = set(issue_map.keys())
    rev_iid = build_reverse_index(issue_map)

    for gl_issue in gl_issues:
        gl_iid = gl_issue["iid"]
        gl_labels = gl_issue.get("labels", [])
        item_type = "issue"
        for lbl in gl_labels:
            if lbl.startswith("type::"):
                t = lbl.split("::", 1)[1]
                if t in ("issue", "feature", "question"):
                    item_type = t

        # Resolve GL milestone → local milestone ID
        gl_milestone = gl_issue.get("milestone")
        ms_local_id: str | None = None
        if gl_milestone:
            ms_local_id = ms_rev.get(gl_milestone["id"])

        slug = slugify(gl_issue["title"])
        expected_file = f"{item_type}-{gl_iid:03d}-{slug}.md"
        local_path = WORKITEMS_DIR / expected_file

        if expected_file in known_fnames or gl_iid in rev_iid:
            # Already tracked — update frontmatter milestone if needed
            if not dry_run and gl_iid in rev_iid:
                existing_fname = rev_iid[gl_iid]
                existing_path = WORKITEMS_DIR / existing_fname
                if existing_path.exists():
                    text = existing_path.read_text(encoding="utf-8")
                    fm_meta, fm_body = parse_frontmatter(text)
                    if ms_local_id and fm_meta.get("milestone") != ms_local_id:
                        fm_meta["milestone"] = ms_local_id
                        existing_path.write_text(
                            render_frontmatter(fm_meta) + fm_body.lstrip(),
                            encoding="utf-8",
                        )
            continue

        if local_path.exists():
            issue_map[expected_file] = map_entry(gl_iid, gl_issue["state"], ms_local_id)
            known_fnames.add(expected_file)
            rev_iid[gl_iid] = expected_file
            continue

        if not dry_run:
            content = make_work_item_file(gl_issue, gl_iid, ms_local_id)
            local_path.write_text(content, encoding="utf-8")

        issue_map[expected_file] = map_entry(gl_iid, gl_issue["state"], ms_local_id)
        known_fnames.add(expected_file)
        rev_iid[gl_iid] = expected_file

        pulled.append(
            {"file": expected_file, "iid": gl_iid, "title": gl_issue["title"]}
        )
        print(f"  PULL  → {expected_file}")

    return pulled


def pull_milestones(
    client: GitLabClient, milestone_map: dict, dry_run: bool
) -> list[dict]:
    """Fetch all GitLab milestones and create local files for unknowns."""
    gl_milestones = client.fetch_all_milestones()
    pulled: list[dict] = []
    rev_ms = {map_get_iid(v): k for k, v in milestone_map.items()}

    known_mids: set[str] = set(milestone_map.keys())

    for gl_ms in gl_milestones:
        title = gl_ms["title"]
        gl_iid = gl_ms["iid"]

        # Try to extract Mxxx from title
        mid_m = re.search(r"(M\d+)", title)
        if not mid_m:
            continue  # not our naming convention, skip
        mid = mid_m.group(1)

        # Skip if already tracked by ID or by GitLab IID
        if mid in known_mids or gl_iid in rev_ms:
            continue

        slug = slugify(title.replace(mid, "").strip("- "))
        expected_file = f"{mid}-{slug}.md"
        local_path = MILESTONES_DIR / expected_file

        if local_path.exists():
            milestone_map[mid] = map_entry(gl_iid, gl_ms.get("state"))
            known_mids.add(mid)
            rev_ms[gl_iid] = mid
            continue

        if not dry_run:
            content = make_milestone_file(gl_ms)
            local_path.write_text(content, encoding="utf-8")

        milestone_map[mid] = map_entry(gl_iid, gl_ms.get("state"))
        known_mids.add(mid)
        rev_ms[gl_iid] = mid

        pulled.append({"file": expected_file, "mid": mid, "title": title})
        print(f"  PULL  → {expected_file}")

    return pulled


# ---------------------------------------------------------------------------
# Push: Local → GitLab
# ---------------------------------------------------------------------------


def _write_frontmatter(
    item: dict, iid: int, issue_map: dict, milestone: str, filename: str
) -> None:
    """Write or update frontmatter in the local file and store milestone in map."""
    path = WORKITEMS_DIR / filename
    if not path.exists():
        issue_map[filename] = map_entry(iid, item["state"], milestone or None)
        return

    text = path.read_text(encoding="utf-8")
    prefix = item["item_type"].upper()
    item_id = f"{prefix}-{iid:03d}"

    # Parse existing frontmatter first; strip milestone if no longer set
    existing_fm, body = parse_frontmatter(text)
    if not milestone and "milestone" in existing_fm:
        del existing_fm["milestone"]

    fm = {
        "id": item_id,
        "status": item["status"].capitalize() if item["status"] else "Open",
        "priority": item["priority"] or "Medium",
        "type": item["item_type"],
    }
    if milestone:
        fm["milestone"] = milestone

    existing_fm.update(fm)
    text = render_frontmatter(existing_fm) + body.lstrip()
    path.write_text(text, encoding="utf-8")
    issue_map[filename] = map_entry(iid, item["state"], milestone or None)


def push_issues(
    client: GitLabClient,
    items: list[dict],
    issue_map: dict,
    milestone_map: dict,
    milestone_index: dict[str, dict],
    dry_run: bool,
) -> bool:
    """Push local work items to GitLab. Returns True if map changed."""
    changed = False

    # Build reverse mapping: item ID -> local milestone IDs
    item_to_milestones: dict[str, list[str]] = {}
    for ms in milestone_index.values():
        for iid_ref in ms["item_ids"]:
            item_to_milestones.setdefault(iid_ref, []).append(ms["id"])

    # Forward lookup: filename → IID from the map
    fwd = dict(issue_map)

    # Build milestone reverse for resolving GL milestone on update

    for item in items:
        key = item["file"]

        # Also try to look up by reverse index (in case file was renamed outside)
        existing_raw = fwd.get(key)
        existing_iid = map_get_iid(existing_raw) if existing_raw is not None else None
        if existing_iid is None:
            wid = item["id"]
            for fname, iid_val in fwd.items():
                wid_in_fname = re.match(r"^(?:issue|feature|question)-(\d+)", fname)
                if wid_in_fname and f"{int(wid_in_fname.group(1)):03d}" in wid:
                    existing_iid = map_get_iid(iid_val)
                    break

        labels = build_labels(item)

        # Determine milestone_id for this issue
        gl_ms_iid = None
        item_milestone = item.get("milestone") or ""
        if not item_milestone:
            # Fall back to milestone files
            item_id = item["id"]
            if item_id in item_to_milestones:
                item_milestone = item_to_milestones[item_id][0]
        if item_milestone:
            ms_raw = milestone_map.get(item_milestone)
            if ms_raw is not None:
                gl_ms_iid = map_get_iid(ms_raw)

        if existing_iid is not None:
            existing_iid = int(existing_iid)
            label = f"UPDATE  #{existing_iid}"
            if not dry_run:
                try:
                    client.update_issue(
                        existing_iid,
                        item["full_title"],
                        item["description"],
                        item["state"],
                        labels=labels,
                        milestone_id=gl_ms_iid,
                    )
                except requests.HTTPError as exc:
                    print(f"  FAIL   #{existing_iid}  {exc}")
                    continue

            # Rename local file to match GitLab IID
            new_file = ensure_filename_matches_iid(
                item, existing_iid, issue_map, dry_run
            )
            if new_file:
                changed = True
                item["file"] = new_file
                key = new_file

            # Write updated frontmatter
            if not dry_run:
                _write_frontmatter(item, existing_iid, issue_map, item_milestone, key)
        else:
            label = "CREATE "
            if not dry_run:
                gl = client.create_issue(
                    item["full_title"],
                    item["description"],
                    item["state"],
                    labels=labels,
                )
                iid = gl["iid"]
                label += f" → #{iid}"
                changed = True

                # Attach to milestone after creation
                if gl_ms_iid is not None:
                    try:
                        client.update_issue(
                            iid,
                            item["full_title"],
                            item["description"],
                            item["state"],
                            milestone_id=gl_ms_iid,
                        )
                    except requests.HTTPError:
                        pass

                # Rename local file to match GitLab IID
                new_file = ensure_filename_matches_iid(item, iid, issue_map, dry_run)
                if new_file:
                    item["file"] = new_file
                    key = new_file

                # Write frontmatter into the file and store milestone in map
                _write_frontmatter(item, iid, issue_map, item_milestone, key)

        state_char = item["state"][:1].upper()
        print(f"  {label}  [{state_char}]  {item['full_title']}")

        # Move closed items to archive
        if item["state"] == "closed":
            src_path = WORKITEMS_DIR / item["file"]
            archived_path = ARCHIVE_DIR / item["file"]
            if src_path.exists() and not dry_run:
                src_path.rename(archived_path)

    return changed


def push_milestones(
    client: GitLabClient, milestones: list[dict], milestone_map: dict, dry_run: bool
) -> bool:
    """Push local milestones to GitLab. Returns True if map changed."""
    changed = False

    for ms in milestones:
        existing_raw = milestone_map.get(ms["id"])
        existing_iid = map_get_iid(existing_raw) if existing_raw is not None else None

        # Build description from full content
        description = ms["content"]

        if existing_iid is not None:
            label = f"UPDATE  #{existing_iid}"
            if not dry_run:
                try:
                    client.update_milestone(existing_iid, ms["title"], description)
                except requests.HTTPError as exc:
                    print(f"  FAIL   #{existing_iid}  {exc}")
                    continue
        else:
            label = "CREATE "
            if not dry_run:
                gl = client.create_milestone(ms["title"], description)
                mid_iid = gl["iid"]
                milestone_map[ms["id"]] = map_entry(mid_iid, gl.get("state"))
                label += f" → #{mid_iid}"
                changed = True

        print(f"  {label}  {ms['title']}")

    return changed


def push_labels(client: GitLabClient, dry_run: bool) -> None:
    """Ensure all label definitions exist in GitLab."""
    if not dry_run:
        client.ensure_labels(all_label_defs())
    print(
        f"  {'[DRY RUN] ' if dry_run else ''}Labels ensured ({len(all_label_defs())} definitions)"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    dotenv.load_dotenv(".gitlab.env")

    gitlab_url = os.environ.get("GITLAB_URL", "https://gitlab.com")
    token = os.environ.get("GITLAB_TOKEN")
    project = os.environ.get("GITLAB_PROJECT")
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

    if not token or not project:
        print("ERROR: GITLAB_TOKEN and GITLAB_PROJECT must be set.", file=sys.stderr)
        sys.exit(1)

    client = GitLabClient(gitlab_url, token, project)
    issue_map = load_map(MAP_FILE)
    milestone_map = load_map(MILESTONE_MAP_FILE)
    map_ensure_migrated(issue_map)
    map_ensure_migrated(milestone_map)

    # Scan local files
    items = scan_work_items()
    milestones = scan_milestones()
    milestone_index = build_milestone_index(milestones)

    if not items and not milestones:
        print("No work items or milestones found.")
        return

    print(
        f"{'[DRY RUN] ' if dry_run else ''}"
        f"Syncing {len(items)} work items + {len(milestones)} milestones "
        f"to {gitlab_url} / {project}\n"
    )

    # ---- Cleanup duplicate files from buggy pulls ----
    print("── Cleanup ──")
    dupes_removed = cleanup_pull_duplicates(issue_map, dry_run)
    if dupes_removed:
        # Re-scan since files changed
        items = scan_work_items()

    # ---- Labels ----
    print("\n── Labels ──")
    push_labels(client, dry_run)

    # ---- Milestones (push) ----
    print("\n── Milestones (local → GitLab) ──")
    ms_changed = push_milestones(client, milestones, milestone_map, dry_run)

    # ---- Issues (push) ----
    print("\n── Issues (local → GitLab) ──")
    issue_changed = push_issues(
        client,
        items,
        issue_map,
        milestone_map,
        milestone_index,
        dry_run,
    )

    # ---- Pull ----
    print("\n── Issues (GitLab → local) ──")
    pulled_issues = pull_issues(client, issue_map, milestone_map, dry_run)

    print("\n── Milestones (GitLab → local) ──")
    pulled_milestones = pull_milestones(client, milestone_map, dry_run)

    # ---- Save maps ----
    map_changed = (
        dupes_removed
        or issue_changed
        or ms_changed
        or pulled_issues
        or pulled_milestones
    )

    if map_changed and not dry_run:
        save_map(MAP_FILE, issue_map)
        save_map(MILESTONE_MAP_FILE, milestone_map)
        print(f"\nMaps updated: {MAP_FILE}, {MILESTONE_MAP_FILE}")
    elif dry_run:
        print("\n(no changes written — dry run)")
    else:
        print("\nDone.")


if __name__ == "__main__":
    main()
