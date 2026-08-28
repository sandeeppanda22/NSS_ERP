# NSS ERP — Participation Lifecycle Rules

---

# Document Metadata

| Item | Value |
|---|---|
| Document Name | Participation Lifecycle Rules |
| Document ID | SOL-LIFE-001 |
| Domain | Solution Lifecycle Standard |
| Repository Path | docs/03_Solution/standards/lifecycle/PARTICIPATION_LIFECYCLE_RULES.md |
| Version | 1.0.0 |
| Status | FROZEN |
| Authority | NSS ERP Project Governance Framework |
| Applies To | Sevak Sangha, Mahila Sangha, Kumari Sangha |

---

# 1. Purpose

Defines common lifecycle rules for Sangha participation when an authoritative Person or NSS Membership lifecycle event occurs.

---

# 2. Scope

Applies to: Sevak Sangha, Mahila Sangha, Kumari Sangha.
Governs system-triggered consequences of: NSS Membership Transfer, Person/Membership Death.
Does not define internal business rules of each Sangha.

---

# 3. Authority Principle

Person and NSS Membership records are authoritative.
Sangha participation shall not contradict authoritative Person/Membership lifecycle.

Person -> NSS Membership -> Current Sakha -> Sangha Participation

---

# 4. Membership Transfer

NSS Membership Transfer is the authoritative event that changes current Sakha.
No independent Sangha transfer workflow exists.

NSS Membership Transfer -> Current Sakha Changes -> Affected Sangha Participation Evaluated

---

# 5. Transfer Impact

When Member transfers Sakha A to Sakha B:

Old Sakha participation:
- Automatically becomes INACTIVE
- Reason = TRANSFERRED_TO_OTHER_SAKHA
- Source = SYSTEM
- No manual intervention required
- Historical record preserved

New Sakha evaluation:
- If new Sakha has applicable Sangha: new current participation may be established
- If new Sakha has no applicable Sangha: no current participation created

---

# 6. Death Impact

When Person/Membership is marked DECEASED:

All active Sangha participation:
- Automatically becomes INACTIVE
- Reason = DECEASED
- Source = SYSTEM
- No separate manual Sangha action required
- Historical record preserved

---

# 7. No Independent Sangha Transfer

There shall be no independent Sevak/Mahila/Kumari transfer workflow.
The authoritative transfer event is NSS Membership Transfer.
Sangha participation changes are system consequences of that event.

---

# 8. Sangha Not Mandatory in Every Sakha

If new Sakha has no corresponding Sangha:
- No current participation created
- Previous history preserved as historical
- No automatic Sangha creation

---

# 9. Status Model

Participation status remains: ACTIVE, INACTIVE.
Transfer and Death are reasons/events, not statuses.

System-generated inactivation reasons:
- TRANSFERRED_TO_OTHER_SAKHA
- DECEASED

Manual inactivation reasons remain governed by individual module rules.

---

# 10. Inactivation Source

Every inactivation has a source:
- SYSTEM (transfer, death — no manual intervention)
- MANUAL (authorized user decision with mandatory reason)

---

# 11. Historical Preservation

Neither transfer nor death physically deletes:
- Participation records
- Attendance history
- Activity history
- Organizational association

---

# 12. No Automatic Membership Change

Sangha participation changes shall never independently change:
- NSS Membership Type
- Sangha Sevi ID
- NSS Membership Status
- Current Membership Sakha

Membership Module remains authoritative.

---

# 13. Audit

Every system-triggered lifecycle change shall preserve:
- Event Type, Event Date
- Affected Person, Membership, Participation
- Previous Status, New Status
- Reason, Source = SYSTEM

---

# 14. Idempotency

Repeated processing of same event shall not create duplicates.

---

# 15. Applicability Matrix

| Event | Sevak | Mahila | Kumari |
|-------|-------|--------|--------|
| Transfer Inactivation | Yes | Yes | Yes |
| Death Inactivation | Yes | Yes | Yes |
| Manual Approval Required | No | No | No |
| Independent Sangha Transfer | No | No | No |

---

# 16. Module References

Sevak, Mahila, and Kumari modules shall reference this standard (SOL-LIFE-001) rather than duplicating these rules.

---

# 17. Core Principles

- Person/Membership Lifecycle Is Authoritative
- NSS Membership Transfer Is the Transfer Event
- No Independent Sangha Transfer
- Current Sakha Determines Sangha Context
- Sangha Not Mandatory in Every Sakha
- Old Participation Becomes Historical
- Transfer Inactivation Is System Generated
- Death Inactivation Is System Generated
- Status Remains ACTIVE / INACTIVE
- Transfer and Death Are Reasons, Not Statuses
- History Never Deleted
- All System Actions Audited

---

# End of Document
