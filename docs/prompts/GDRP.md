Review the platform for Swiss DSG (Datenschutzgesetz) and GDPR-adjacent compliance, since this is a Swiss Verein handling member personal data, financial records, and full email archives. This is a REVIEW AND REPORT task first — do not change code or policy until findings are reviewed with me, since some of this may already be intentionally addressed in the Statuten/Mitgliederreglement documents and code shouldn't contradict governance documents without that being a deliberate decision.

## Step 1 — Map what personal data the platform holds

Audit all models/tables that store personal data, and report what's stored where:
   grep -rn "class.*db.Model\|class.*Base" app/backend/vollbuild/models/*.py
For each model (Member, MailLogEntry, AuditLog entries, WildDuck mailbox content via MongoDB, etc.), note: what personal data fields exist, and roughly how sensitive (name/email vs financial vs full email content).

## Step 2 — Check data retention enforcement in code

1. Does deleting a member (soft or permanent delete) actually cascade to:
   - Their WildDuck mailbox and stored email content (or does it persist indefinitely after a member leaves)?
   - Their audit log entries (these likely SHOULD persist for governance/accountability reasons — flag this tension explicitly, don't auto-delete audit trails)
   - Their financial/tier records (likely need retention for accounting/legal reasons — Swiss association bookkeeping requirements — flag, don't blindly delete)
2. Cross-reference against the existing Mitgliederreglement document (referenced in project memory) — does it specify a retention period after membership ends? Does current code enforce that period, or is deletion currently manual/ad-hoc with no automated retention policy?
3. Report: is there currently ANY automated process that purges/anonymizes member data after a defined retention period, or is everything retained indefinitely by default? This is likely the single most important finding to surface clearly.

## Step 3 — Check for a data export ("right to access/portability") path

Does a member have any way — self-service or admin-assisted — to request and receive an export of their own data? Check if this exists anywhere in members/routes.py or as a documented manual admin process. If it doesn't exist at all, this is a gap to report (implementation can be a separate follow-up task).

## Step 4 — Check the mail stack specifically

Given the volume of work already done on WildDuck/Haraka/ZoneMTA in this conversation: when a member leaves the Verein, what happens to their @vollbuild.ch mailbox and its content? Is there a defined process (export then delete, archive for N months then delete, immediate delete, indefinite retention)? This is both a DSG question and a practical one (storage growth over time as members come and go).

## Step 5 — Report only, no implementation yet

Produce a findings report covering Steps 1-4, explicitly flagging:

- Where automated enforcement is MISSING (these are real gaps)
- Where current code behavior might CONFLICT with what the Statuten/Mitgliederreglement documents promise members
- Recommended next steps, but do not implement any retention/deletion automation until I review and confirm the policy specifics (retention periods, what gets deleted vs anonymized vs archived) — this needs a governance decision, not just an engineering one.
