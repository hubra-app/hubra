Perform a thorough code review and cleanup pass across the entire backend (app/backend/vollbuild/) following industry standards for Python/Flask applications. This is a quality and maintainability pass, not a feature change — preserve all existing behavior unless a bug is found, in which case flag it explicitly before fixing.

## Scope

Run this across app/backend/vollbuild/ in its entirety: api/, models/, services/ (if created from the prior service-layer refactor), tasks/, and any top-level modules (__init__.py, extensions.py, etc.).

## Step 1 — Static analysis baseline

1. Run pylint across the codebase and capture the full report:
   docker compose exec -T backend python -m pylint vollbuild/ --output-format=text > /tmp/pylint_report.txt

   If pylint isn't installed, install it as a dev dependency first and confirm it's added to the appropriate requirements/dev file (e.g. requirements-dev.txt or pyproject.toml dev dependencies) rather than just installing ad-hoc.

2. Also run flake8 or ruff if either is already configured in the project (check for .flake8, ruff.toml, or pyproject.toml [tool.ruff] sections) — use whatever linter is already the project's standard rather than introducing a new one. Report which linter(s) are actually configured before proceeding so we use the right one.

3. Categorize all findings by severity/type:
   - Errors (real bugs: undefined names, broken imports, unreachable code)
   - Warnings (real risk: bare except, mutable default arguments, broad exception catching, unused imports/variables)
   - Conventions (naming, docstrings, line length, import order)
   - Refactor suggestions (too-many-arguments, too-many-branches, duplicate-code, too-complex functions)

   Report the full categorized summary (counts per category, not necessarily every single line) before fixing anything, so I have visibility into the scale of changes before they happen.

## Step 2 — Fix in priority order

Fix in this order, and at the end of each category, rebuild + run the test suite to confirm nothing broke before moving to the next:

1. __Errors first__ — these are likely real bugs. Fix immediately. If any look risky or ambiguous (e.g. unclear whether removing "unreachable" code is safe, or whether an undefined name is a typo vs an intentional dynamic reference), flag and ask rather than guessing.

2. __Warnings__ — fix these with industry-standard patterns:
   - Bare `except:` → replace with specific exception types, or `except Exception:` at minimum with a comment on why it's broad
   - Mutable default arguments (`def f(x=[])`) → replace with `None` default + assign inside function body
   - Unused imports/variables → remove (but double check they're not used via dynamic access, string references, or re-exported for other modules to import)
   - Broad `except Exception: pass` (silent failure) → at minimum log the exception; flag any case where silently swallowing an error seems like it could be hiding a real production bug we should know about, given we just spent considerable effort debugging silent failures (the WildDuck "messages" vs "total" field bug, the SRS REWRITE_DOMAIN issue) that could have been caught faster with proper logging
   - String formatting: prefer f-strings consistently if the codebase already mostly uses them; flag if there's a mix of %-formatting, .format(), and f-strings so we can standardize

3. __Conventions__:
   - Consistent docstring style (check what's already dominant in the codebase — Google style, NumPy style, or plain — and standardize on that rather than introducing a new style)
   - Import ordering (standard library → third-party → local, alphabetized within groups) — use isort if available/configured, otherwise apply manually following PEP 8
   - Naming conventions (snake_case for functions/variables, PascalCase for classes — flag any violations)
   - Line length — follow whatever max-line-length is configured (check pylintrc/pyproject.toml); if unconfigured, default to 100 or 120 (not the old PEP8 79) and ask which the team prefers if truly unset

4. __Refactor suggestions__ — apply selectively, not blindly:
   - too-many-arguments / too-many-branches / too-complex (high cyclomatic complexity): for each flagged function, assess whether splitting it actually improves readability or whether the complexity is inherent to the problem (e.g. the mail_sync task naturally has several sequential steps — don't fragment it into tiny functions if that hurts readability more than it helps)
   - duplicate-code: this is the most actionable category given we already did a service-layer refactor — check whether pylint's duplicate-code findings overlap with logic that should have been consolidated into a Service class but wasn't yet (e.g. did we miss any blueprints in the earlier service-layer refactor pass?)
   - For any function/class you simplify, show before/after and a one-line reason (e.g. "extracted validation into helper — was duplicated in 3 route handlers" or "replaced manual dict building with dataclass — clearer intent, type-checked")

## Step 3 — Things to specifically look for beyond pylint's default checks

Given the codebase's history (heavy mail/WildDuck integration, Celery tasks, recent service-layer refactor), also manually review for:

1. __Inconsistent error handling patterns__ — confirm the WildDuckError handling pattern is applied consistently everywhere WildDuck is called (not sometimes caught, sometimes not)
2. __N+1 query patterns__ — especially in any loop that queries the DB or calls WildDuck per-iteration (we saw this pattern in mail_sync.py looping over members and calling WildDuck per member — confirm this is necessary vs batchable, and if necessary, confirm it's documented why)
3. __datetime handling consistency__ — confirm everything uses timezone-aware datetimes (datetime.now(timezone.utc)) consistently following any fixes from the earlier pytest warnings pass; flag any stragglers
4. __SQLAlchemy session management__ — confirm commits happen in one consistent place (established in the service-layer refactor) and there's no leftover code committing/rolling back inconsistently
5. __Type hints__ — check current type hint coverage; if the codebase is already mostly type-hinted, fill in obvious gaps; if it's sparse/inconsistent, report the current state and ask whether full type-hint coverage is in scope for this pass or a separate effort (this can be a large undertaking, don't silently take it on)
6. __Security-relevant patterns__ — flag (don't necessarily fix without confirmation) any: hardcoded secrets/tokens that should be env vars, SQL string concatenation instead of parameterized queries, missing input validation on user-supplied data that reaches WildDuck or shell commands

## Step 4 — Reporting

Provide a final summary with:

- Total pylint score before/after (pylint reports a /10 score)
- Count of issues fixed per category (errors, warnings, conventions, refactors)
- List of any issues found but NOT fixed, with reasoning (e.g. "flagged as too risky to auto-fix," "needs product decision," "out of scope — type hints")
- Any newly discovered bugs found during this review (separate from style/lint issues) — these are the most important findings, surface them clearly at the top of your summary, not buried at the end
- Confirm full test suite still passes and pylint/flake8/ruff (whichever is the project's actual linter) now reports significantly fewer issues, ideally near-zero for errors/warnings categories

Work through this incrementally (not one giant uncommitted change) — after each major category of fixes, rebuild the backend container and run tests to catch regressions early rather than discovering them after a huge batch of changes:
   docker compose build backend
   docker compose exec -T backend python -m pytest -ra

Start with Step 1 (the baseline report) and share the categorized summary before fixing anything, so I can see the scale and flag any category I want deprioritized or handled differently before you proceed.
