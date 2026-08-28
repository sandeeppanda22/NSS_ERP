# Solution Lifecycle Standards

Cross-cutting SOLUTION-layer lifecycle rules that apply *across* modules, rather than living
inside any single module's own business-rules document. Both documents here are **FROZEN**,
v1.0.0.

## Documents

- **`PERSON_LIFECYCLE_RULES.md`** (`SOL-LIFE-002`) — the authoritative rule for what happens
  system-wide when a Person is marked `DECEASED`. Death is recorded once, only at the Person
  level (never as a separate manual action inside Membership/Sevak/Mahila/Kumari/Kishor/
  Governance/Family/Attendance) and propagates from there. No permanent ID (Person ID, Sangha
  Sevi ID, Kumari ID, Kishor ID) is ever deleted or changed — a deceased person's ID persists
  with `Status: DECEASED`. Nothing is physically deleted; history is preserved throughout.
- **`PARTICIPATION_LIFECYCLE_RULES.md`** (`SOL-LIFE-001`) — the shared rule for how Sevak
  Sangha, Mahila Sangha, and Kumari Sangha *participation* records react to two authoritative
  triggers: NSS Membership Transfer (old Sakha's participation goes `INACTIVE`, reason
  `TRANSFERRED_TO_OTHER_SAKHA`; new Sakha is evaluated for a new participation record) and
  Person/Membership death (reason `DECEASED`) as defined in `SOL-LIFE-002`. There is
  deliberately no independent Sevak/Mahila/Kumari transfer workflow — NSS Membership Transfer is
  the only authoritative transfer event; Sangha participation change is a system-generated
  consequence of it, never a manual per-Sangha action.

## Relationship between the two documents

`SOL-LIFE-002` (Person) is the trigger; `SOL-LIFE-001` (Participation) defines the downstream
effect on Sevak/Mahila/Kumari participation records specifically. Membership Transfer is handled
only in `SOL-LIFE-001`, since it's a Sakha-level event, not a Person-level one.

## Relationship to module business rules

Sevak, Mahila, and Kumari module business-rules documents (`docs/03_Solution/modules/{sevak,
mahila,kumari}/`) are expected to **reference** `SOL-LIFE-001` rather than duplicate its rules.
Neither document here has yet been cross-referenced from those module READMEs — see
`docs/PROJECT_DOCUMENTATION.md` for the current cross-reference gap.

## Status

Both documents are Authority: `NSS ERP Project Governance Framework`, Status: `FROZEN`. This
folder itself is not module-specific — see `docs/03_Solution/modules/README.md` for the module
index; this is a companion cross-module standard, not a 20th module.
