A few more that round things out, grouped by how urgent they actually are for a Verein platform handling money and member trust:
Near-term, low effort, high value:

A documented runbook/onboarding doc for "what happens when Mike isn't available." This entire conversation is a single person debugging an increasingly sophisticated stack solo. If you're hit by a bus (or just on vacation during an incident), does anyone else in the Verein know how to SSH in, restart a service, or even where the docker-compose files live? Worth a docs/operations.md covering: where things run, how to deploy, how to check logs, who has VPS access, where secrets/.env live.
Secrets management audit. Right now .env files with WILDDUCK_API_TOKEN, JWT_SECRET_KEY, SMTP passwords etc. live directly on the VPS filesystem and presumably get edited by hand. Worth checking: are these committed to git anywhere by accident? Is there a .gitignore entry for .env? Is there more than one copy of secrets drifting between your local machine and the VPS?

Medium-term:

CI pipeline. Nothing in this conversation suggests automated testing/linting runs before changes hit production — everything appears to be built, then docker compose up -d directly on vps-public-matterhorn. Given the pytest/pylint work already done, wiring those into a GitHub Actions workflow that blocks merge on failing tests would lock in the quality bar rather than relying on remembering to run them manually each time.
Log aggregation/retention. Right now diagnosing anything means docker compose logs scrollback, which is ephemeral and gets lost on container restart. A lightweight log shipper (even just docker compose logs piped to a rotated file, or something like Dozzle for a simple web log viewer) would have made several of the debugging sessions in this conversation faster.

Lower priority / nice-to-have:

Dependency update automation (Dependabot or Renovate) given this stack pulls from npm, pip, and several Docker base images — staying current matters more once you have real member data and payment/tier info in play.
A formal incident/postmortem habit for anything that causes member-visible downtime (mail not delivering, site down) — doesn't need to be heavy, just a short note in a shared doc each time something breaks, so patterns become visible over months rather than being forgotten.
