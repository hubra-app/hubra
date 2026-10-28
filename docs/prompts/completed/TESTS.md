## Step 1 — Inventory and report before changing anything

1. List every test file (flat and in subdirectories) with its current name, and for each, identify what feature/domain it actually tests by reading the test names/docstrings inside, not just guessing from the filename:
   find app/backend/tests/ -name "test_*.py" -o -name "conftest.py" | sort

2. For files with sprint/milestone/issue-number prefixes (s01, s02, s03, s04 — appearing twice with DIFFERENT suffixes (test_s04_mail_wiring.py vs test_s04_email.py), s05, s06, s11, s12, m003, m005, issue022), figure out and report:
   - What does the prefix actually mean in this project's history (sprint number? milestone? Has this convention been used consistently or did it drift?)
   - Whether two files sharing a prefix (e.g. the two s04 files, or s02 appearing as both test_s02_club_username_password.py and test_s02_auth_hardening.py) test genuinely separate things that happen to fall in the same sprint, or whether there's actual overlap/duplication between them — flag any suspected duplicate coverage explicitly

3. For the four subdirectories (members/, mail/, groups/, account/), list their contents:
   ls -la app/backend/tests/members/ app/backend/tests/mail/ app/backend/tests/groups/ app/backend/tests/account/
   Report whether these directories have their own naming convention (consistent or not), and whether any of their tests overlap with the flat top-level files testing the same domain (e.g. is there overlap between tests/members/ and the flat test_members.py?).

4. Report a full categorization: which files map to which actual backend blueprint/domain (auth, members, groups, mail, finance, polls, inventory, health, settings, audit, roles/permissions, account) based on what they actually test, regardless of current filename.

Do not rename or move anything yet — report findings first so I can confirm the categorization is correct before the directory structure changes under it.

## Step 2 — Propose the new convention

Propose (and get my confirmation before implementing) a structure mirroring app/backend/vollbuild/api/<blueprint>/ — one test directory per blueprint, matching the blueprint names we already established during the service-layer refactor (applications, audit, auth, categories, dashboard, events, finance, groups, health, inventory, mail, members, notifications, polls, roles, settings, system, tiers):
app/backend/tests/

conftest.py

auth/

test_login.py

test_registration.py

test_password_reset.py

test_rate_limiting.py

...

members/

test_crud.py

test_lifecycle.py

test_permissions.py

...

mail/

test_wiring.py

test_wildduck_client.py

test_mailbox_sync.py

...

finance/

test_transactions.py

test_invoices.py

...

...
Within each blueprint directory, file names should describe WHAT is tested (test_login.py, test_rate_limiting.py) not WHEN it was written (no more s01/s04/m003/issue022 prefixes) — sprint/issue numbers belong in git history and commit messages, not permanently embedded in filenames, since they become meaningless context six months later and as we've seen, collide/duplicate (two unrelated "s04" files).

For tests that don't map cleanly to a single blueprint (e.g. test_s11_backend_gaps.py, test_s12_bootstrap_disable.py — these sound like cross-cutting or app-bootstrap-level tests rather than domain tests), propose where they belong: either a top-level tests/system/ or tests/bootstrap/ directory, or distributed into the relevant blueprint dirs if their content actually belongs there once you read what they test. Report your proposed destination for each ambiguous file specifically and let me confirm before moving.

## Step 3 — Implement the migration

1. Move/rename files according to the confirmed Step 2 structure using git mv (not delete+recreate) so file history is preserved:
   git mv app/backend/tests/test_auth.py app/backend/tests/auth/test_core.py
   (etc. for every file)

2. For the two s04 files and any other suspected-duplicate-coverage pairs flagged in Step 1, after moving them into the same blueprint directory, review whether they should actually be merged into one file, or kept separate because they genuinely test different things — make this call file-by-file and report what you decided and why.

3. Update conftest.py and any test configuration (pytest.ini, pyproject.toml [tool.pytest.ini_options], setup.cfg) if file discovery patterns or fixture scoping depend on the old flat structure.

4. Check for and fix any cross-references between test files (e.g. one test file importing a fixture or helper defined in another test file by its old path/name):
   grep -rn "from tests\.\|import tests\." app/backend/tests/

## Step 4 — Verify

1. Run the full suite and confirm the same number of tests collect and pass as before the reorganization (no tests silently lost or broken by the move):
   python -m pytest --collect-only -q | tail -5
   python -m pytest -ra

2. Compare test count before/after — if the count doesn't match, find out why before considering this done.

## Step 5 — Document the convention going forward

Add a short section to whatever contributor/development doc exists (or create app/backend/tests/README.md if none exists) stating the convention clearly: one directory per API blueprint, files named by what they test not when they were written, so this doesn't drift back into the s01/m003/issue022 mess over time.

Report back: final directory structure, every file's old → new path mapping, any files merged together with reasoning, any ambiguous-placement decisions made, and confirmation that pytest collects and passes the same total test count before and after.
