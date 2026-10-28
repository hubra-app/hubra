Implement Swiss QR-bill invoice generation for membership dues, reading creditor/club details from the new settings/club/* namespace (Prompt 1 — must be completed and confirmed working first) and integrating with the existing finance/tiers invoice model.

## Prerequisites — confirm before writing any code

1. **Prompt 1 (Club Settings Namespace) must be done and verified first.** This prompt depends on club/iban, club/address_*, club/name, and club/finance_email being readable from the settings system. Do not proceed until that's confirmed working.

2. **QR-IBAN in hand.** Confirm with the Verein's treasurer whether the club's bank account has a QR-IBAN issued (required for QRR references — a regular IBAN will be rejected by banks for QRR-referenced payments). If not yet issued, this is a blocking prerequisite — most Swiss banks provide one free on request, but it needs to exist before club/iban is populated with a real, usable value.

3. **Structured member addresses.** Swiss QR-bill spec requires structured debtor address fields (street, house number, postal code, city, country as separate fields), not free-text. Check the current Member model:
   grep -n "address" app/backend/vollbuild/models/member.py
   If address is currently unstructured, this needs to be split into structured fields as part of this work, with a data migration for existing members. Report current state and required migration scope before proceeding — confirm with me, since this may be a non-trivial change touching existing member records and any UI that currently collects/displays address as a single field.

## Step 1 — Reference number scheme

1. Implement a deterministic, reversible QRR reference generator/parser as a utility module (e.g. vollbuild/services/qr_reference.py) — not a separate database table. The reference must be derivable purely from the Invoice/Transaction model's existing primary keys (member_id, invoice_id), so it's generated on demand with nothing extra to keep in sync.

2. Design: encode member_id and invoice_id into the 27-digit QRR numeric reference (digits only, with a mod-10-recursive check digit as the final digit per the Swiss spec). Propose the exact digit allocation (e.g. 8 digits for member_id, remaining digits minus the check digit for invoice_id, zero-padded) sized generously to never realistically overflow at this Verein's scale. Confirm the allocation with me before implementing — changing it later breaks any already-issued references, since old invoices' QR-bills would no longer match the new encoding.

3. Implement:
   - generate_qrr_reference(member_id: int, invoice_id: int) -> str
   - parse_qrr_reference(reference: str) -> tuple[int, int] — validates the check digit, raises a clear error on malformed/tampered input
   - validate_qrr_checksum(reference: str) -> bool

4. Write thorough unit tests for the check-digit algorithm specifically, including against known-correct reference examples from official SIX documentation if available (not just self-generated round-trip tests, since a self-consistent-but-wrong implementation would pass round-trip tests while still failing real-world bank validation).

## Step 2 — QR-bill PDF generation

1. Add the qrbill Python library as a dependency, pinned in requirements:
   grep -n "qrbill" app/backend/requirements*.txt

2. Implement a generation function (e.g. vollbuild/services/qr_bill.py) taking an Invoice record and producing a compliant QR-bill PDF:
   - Creditor info: read from settings/club/iban, club/name, club/address_* (Prompt 1)
   - Debtor info: read from the Member's structured address (per Prerequisite 3)
   - Amount: the invoice amount, CHF
   - Reference: generate_qrr_reference(member_id, invoice_id) from Step 1
   - Additional info: a short description (e.g. membership year/period — match Swiss German glossary conventions from earlier translation work if applicable)

3. Validate the qrbill library output against the strict SIX layout spec (105mm x 148mm payment part, correct QR module sizing, Swiss cross overlay) — generate a test PDF and check actual dimensions, since incorrect layout risks rejection by bank/postal scanners.

4. Decide and confirm: standalone QR-bill PDF, or merged onto a fuller itemized invoice document? If merging, the QR-bill payment part needs exact SIX-spec positioning at the bottom of the page, not just appended as a separate page.

## Step 3 — Delivery

1. Reuse the existing SMTP/ZoneMTA mail-sending infrastructure to attach the generated PDF to an invoice email, with the from-address/finance contact pulled from settings/club/finance_email.
2. Add GET /api/v1/finance/invoices/<id>/qr-bill.pdf for on-demand regeneration/redownload.
3. Surface a "Download QR-bill" button per outstanding invoice on the member's own invoice/dues view (under Account, per the earlier dashboard/account merge).

## Step 4 — Reconciliation scope (confirm before building)

**Option A — Manual reconciliation (recommended for this pass).** Admin/treasurer manually marks invoices paid after checking the bank account. No camt.054 parsing built yet.

**Option B — camt.054 auto-reconciliation.** Parse the Swiss bank's camt.054 ISO 20022 export, match incoming payment references via parse_qrr_reference() from Step 1, auto-mark matched invoices paid. Requires confirming the Verein's specific bank supports camt.054 export, an admin upload UI, and explicit handling for amount mismatches (partial/overpayment) — flag for manual review rather than silently auto-resolving.

Confirm which option before implementing. Recommend Option A first, Option B as a follow-up once Steps 1-3 are validated against a real invoicing cycle.

## Step 5 — Verify

1. Generate a test QR-bill PDF, validate against official SIX layout dimensions
2. Test-scan the generated QR code with a real Swiss banking app if possible, confirm correct pre-fill of IBAN, amount, reference
3. Confirm generate_qrr_reference / parse_qrr_reference round-trip correctly and match known-correct check-digit examples
4. Confirm end-to-end: creditor details correctly sourced from settings/club/* (Prompt 1), debtor details from structured member address, generated reference correctly round-trips to the right member+invoice
5. Run full test suite; add strong coverage for the reference-number module specifically, given a subtle bug here could generate references that look valid but get silently rejected or — worse — misattributed to the wrong member/invoice

## Step 6 — Report

Confirm: digit allocation chosen for the reference scheme, address-structuring migration outcome, QR-bill PDF validation results, and which reconciliation scope (A or B) was implemented.

Wait for my confirmation on: the QR-IBAN prerequisite being in hand, the reference-number digit allocation, the address-structuring migration scope, and reconciliation scope (A vs B) — before beginning implementation.
