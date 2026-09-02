# NSS ERP Mahila Sangha Module

Status: DRAFT — BYE-LAW ALIGNED, Version 2.1.0 across all 5 documents. Full Solution design
complete; there is still no `backend/mahila/` Django app. Mahila members use the same
Probationary/Regular/Associate membership framework as everyone else — no separate membership
system.

---

## Documents

01_mahila_module_overview.md — Document ID `SOL-MAH-001`, v2.1.0
02_mahila_erd.md — Document ID `SOL-MAH-002`, v2.1.0
03_mahila_lifecycle.md — Document ID `SOL-MAH-003`, v2.1.0
04_mahila_business_rules.md — Document ID `SOL-MAH-004`, v2.1.0
05_mahila_table_design.md — Document ID `SOL-MAH-005`, v2.1.0

Purpose (all 5): Membership, Activities, and Governance for the Mahila Sangha via the central
**Mahila Parichalana Mandali** — the single Governing Body that governs every local Mahila
Sangha across all Sakha Sanghas (per `REF-001` Clause 12 and `REF-MS-6(i)`–`REF-MS-6(viii)`).

---

## v2.1.0 governance-model correction (supersedes v2.0.0)

**Mahila Governing Body = Mahila Parichalana Mandali — one body, two names, one governance
record.** An earlier v2.0.0 pass had incorrectly modeled these as two separate bodies (the
Mandali as a distinct three-year body); v2.1.0 corrects this to match the Bye-Law, per
`04_mahila_business_rules.md` MAH-019 ("Same Body") and MAH-094 (retiring the superseded
two-body interpretation), and enforced at the schema level in `05_mahila_table_design.md` (no
separate `mahila_governing_body` + `mahila_parichalana_mandali` tables).

Confirmed structure: **9-member Governing Body** (President, Vice-President, Parichalak,
Secretary, Joint Secretary, Treasurer, 3 Members), **2-year term**, continuing until the
successor takes over.

---

## Current Status

Design Complete · ERD Complete · Lifecycle Documented · Business Rules Drafted (governance model
corrected v2.0.0 → v2.1.0) · Table Design Drafted · SQL Implementation Not Started ·
`backend/mahila/` Django app does not exist yet
