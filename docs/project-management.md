# Project Management

This project uses **GSD (Guided Software Development)** — an AI-assisted
workflow framework.

## GSD workflow

Work is organized into phases following the cycle:

```
Discuss → Plan → Execute → Verify
```

- **Phases**: Each phase has a discussion, plan, execution, and verification step
- **Milestones**: Tracked via GitLab work items and merge requests
- **GSD state**: Lives in `.gsd/` (local-only, gitignored)

## AI tooling

Code is developed with **Claude** (Anthropic's AI) and **OpenCode** as
assistants. The `.claude/` and `.opencode/` directories contain agent
configuration; the `.agents/` directory holds project-local skills.

### Agent rules (from `AGENTS.md`)

- Run tests before marking tasks complete
- Never create files outside the project directory
- Ask before deleting a file
- Explain reasoning before writing code
- If unsure, ask — don't guess
- Never commit `.env` or any file containing secrets
- Don't modify `docker-compose.yml` without discussion
- Database migrations live in `app/backend/migrations/` — always generated via
  `flask db migrate`, never hand-edited

## Documentation layout

```
docs/
├── architecture.md            # System architecture & request flow
├── api-overview.md            # API endpoints, auth, permissions
├── frontend.md                # Frontend stack and structure
├── configuration.md           # Environment and settings
├── disaster-recovery.md       # Backup & restore runbook
├── frontend_issues.md         # React review snapshot (tracking)
├── SUBDOMAIN_MIGRATION.md     # Cross-origin auth (CORS, cookies, ProxyFix)
├── project-management.md      # This file
└── prompts/                   # AI planning prompts (internal reference)
    └── completed/             # Resolved work items
```
