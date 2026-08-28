# NSS ERP — Person Lifecycle Rules

---

# Document Metadata

| Item | Value |
|---|---|
| Document Name | Person Lifecycle Rules |
| Document ID | SOL-LIFE-002 |
| Domain | Solution Lifecycle Standard |
| Repository Path | docs/03_Solution/standards/lifecycle/PERSON_LIFECYCLE_RULES.md |
| Version | 1.0.0 |
| Status | FROZEN |
| Authority | NSS ERP Project Governance Framework |
| Applies To | All modules referencing Person |

---

# 1. Purpose

Defines the global lifecycle rule when a Person is marked DECEASED in the NSS ERP.

Death is a Person-level lifecycle event. It is recorded once at the authoritative Person level and propagated system-wide.

---

# 2. Core Rule

When the authoritative Person record is marked DECEASED:

Person.status = DECEASED
    |
    v
Global Lifecycle Event
    |
    v
All applicable modules evaluate the Person
    |
    v
All relevant identities / participation records
reflect DECEASED according to their module rules

---

# 3. Single Source of Truth

Death is recorded ONLY at the Person level.

No separate manual deceased action in:
- Membership
- Sevak
- Mahila
- Kumari
- Kishor
- Governance
- Family
- Attendance

The system derives all consequences from: Person.status = DECEASED

---

# 4. Module-Specific Consequences

| Domain | Result |
|--------|--------|
| Person | DECEASED |
| NSS Membership / Sangha Sevi | DECEASED / lifecycle closed |
| Sevak participation | INACTIVE, reason = DECEASED, source = SYSTEM |
| Mahila participation | INACTIVE, reason = DECEASED, source = SYSTEM |
| Kumari participation | INACTIVE, reason = DECEASED, source = SYSTEM |
| Kishor participation | INACTIVE, reason = DECEASED, source = SYSTEM |
| Governance assignment | Automatically ended/inactive |
| Attendance | Historical records preserved |
| Family | Historical relationship preserved |
| Documents | Preserved |
| Audit history | Preserved |

---

# 5. Identity Preservation

No ID is deleted or changed:

- Person ID remains
- Sangha Sevi ID remains
- Kumari ID remains
- Kishor ID remains
- All permanent business identifiers remain

Example: SS00000123 does not disappear. It becomes SS00000123, Status: DECEASED.

---

# 6. Historical Preservation

Death does not physically delete:
- Person record
- Membership record
- Participation records
- Attendance history
- Activity history
- Governance assignment history
- Family relationships
- Documents
- Audit trail

All remain available for reporting, audit, and historical reference.

---

# 7. No Contradictions Allowed

The system must not allow:

Person = DECEASED
Membership = ACTIVE        (contradiction)
Sevak = ACTIVE             (contradiction)
Mahila = ACTIVE            (contradiction)

The Person lifecycle is authoritative. Module statuses must be consistent.

---

# 8. System-Generated

Death-triggered status changes across modules are:
- Source = SYSTEM
- No manual intervention required per module
- Audited automatically

---

# 9. Frozen Global Rule

A deceased Person is globally identified as DECEASED throughout NSS ERP.

Person identity and all permanent IDs remain unchanged.

Module-specific records are automatically transitioned according to their own lifecycle rules.

All historical records, attendance, governance, membership, participation, and audit history are preserved.

---

# 10. Relationship to Participation Lifecycle Rules

SOL-LIFE-001 (Participation Lifecycle Rules) defines what happens to Sevak/Mahila/Kumari participation.

This document (SOL-LIFE-002) defines the authoritative Person-level event that triggers those consequences.

Hierarchy:
Person Lifecycle (this document)
    |
    v
Participation Lifecycle (SOL-LIFE-001)
    |
    v
Module-specific rules

---

# End of Document
