# GOV-001 — Project Governance Principles

## Document Metadata

| Field | Value |
|--------|-------|
| Document Name | Project Governance Principles |
| Document ID | GOV-001 |
| Domain | GOV |
| Repository Path | docs/00_Project_Governance/GOV/GOV-001_Project_Governance_Principles.md |
| Version | 1.2.0 |
| Status | Approved |
| Governance Baseline | v1.0 |
| Authority | NSS ERP Governance Framework |
| Owner | NSS ERP Project |
| Effective Date | TBD |
| Last Updated | 2026-08-14 |

## Revision History

| Version | Date | Author | Description |
|----------|------|--------|-------------|
| 1.0.0 | YYYY-MM-DD | NSS ERP Project | Initial version |
| 1.1.0 | 2026-08-13 | NSS ERP Project | Added GOV-LIFE-006 (Governance Document Status Lifecycle); renamed per-rule `Status` field to `Rule Maturity`; Status advanced from Draft to Approved to reflect actual governance use. See GDR-003. |
| 1.2.0 | 2026-08-14 | NSS ERP Project | Added GOV-ROLE-006 (Final Decision Authority = NSS Governing Body); clarified Project Owner = NSS and Governance Authority = Project Steering Committee. See GDR-004. |

## Table of Contents

1. Purpose
2. Scope
3. Definitions
4. Governance Principles
5. Governance Lifecycle
6. Governance Roles and Responsibilities
7. Governance Compliance

Appendix A – Governance Lifecycle
Appendix B – Document Hierarchy
Appendix C – Governance Responsibility Matrix

## 1. Purpose

The purpose of this document is to establish the governance principles that direct the planning, development, implementation, maintenance, and evolution of the NSS ERP project.

This standard defines the governance framework that ensures all project activities remain aligned with:

- Official NSS Bye-Law
- Authoritative Reference (REF) documents
- Repository governance standards (AUTH)
- Approved project requirements
- Governance Baseline v1.0

This document provides the governing principles for project decision-making, establishes the hierarchy of governance authority, and defines the responsibilities necessary to maintain consistency, traceability, and compliance throughout the project lifecycle.

## 2. Scope

This standard applies to the governance of the NSS ERP project throughout its lifecycle.

It establishes the principles that govern:

- project governance;
- governance authority;
- governance responsibilities;
- governance decision-making;
- governance lifecycle management;
- compliance with authoritative references; and
- governance oversight for project deliverables.

This standard applies to all project domains, including requirements, solution design, implementation, testing, documentation, and releases.

This standard does not define:

- repository management standards (defined in AUTH);
- authoritative statutory content (defined in REF);
- individual governance decisions (recorded in GDR);
- functional business requirements (defined in REQ); or
- technical implementation details (defined in SOLUTION).

These subjects are governed by their respective standards.

## 3. Definitions

For the purposes of this standard, the following definitions apply.

**Governance**

The framework of principles, responsibilities, decision-making processes, and controls used to direct and manage the NSS ERP project.

---

**Governance Baseline**

The approved and controlled set of governance standards that establish how the project shall be governed.

---

**Governance Authority**

The authority responsible for approving governance standards, governance changes, and project governance decisions.

---

**Governance Decision**

A formally approved decision that establishes, modifies, interprets, or clarifies project governance.

---

**Governance Decision Register (GDR)**

The official repository of approved governance decisions affecting the NSS ERP project. The GDR operates as a cross-cutting governance-decision and record-keeping mechanism rather than as a sequential layer within the project lifecycle (see GOV-ORG-002).

---

**Compliance**

The state of conforming to approved governance standards, authoritative references, and documented project policies.

---

**Traceability**

The ability to trace every project artifact back through the governance hierarchy to its originating authority.

---

**Document Status**

The approval-lifecycle state of a governance document as a whole, recorded in its metadata table. See GOV-LIFE-006 for the defined values and their meaning.

---

**Rule Maturity**

An attribute recorded on an individual normative rule within a governance document (e.g. `Frozen`), indicating whether that specific rule's content may be modified without governance change control. Rule Maturity is independent of the Document Status of the document containing the rule, and independent of Decision Status (the lifecycle of an individual Governance Decision Register entry, per GDR-001).

## 4. Governance Principles

The governance principles defined in this section establish the foundational rules that direct all governance activities within the NSS ERP project.

These principles are mandatory unless superseded through the approved governance change process.

### GOV-ORG-001 — Statutory Authority

**Rule Maturity:** Frozen

The Official NSS Bye-Law constitute the highest governing authority for the NSS ERP project.

All governance standards, authoritative references, requirements, solution designs, implementation artifacts, tests, and releases shall remain consistent with the statutory authority.

Where a conflict exists between project documentation and the Official NSS Bye-Law, the statutory authority shall prevail.

---

### GOV-ORG-002 — Governance Hierarchy

**Rule Maturity:** Frozen

The NSS ERP project shall maintain the following governance lifecycle hierarchy:

```text
Official Constitution & Bye-Laws
        │
        ▼
       REF
        │
        ▼
      AUTH
        │
        ▼
       GOV
        │
        ▼
       REQ
        │
        ▼
   SOLUTION
        │
        ▼
      CODE
        │
        ▼
      TEST
        │
        ▼
    RELEASE
```

Each governance layer derives its authority from the layer immediately above it.

Lower governance layers shall not modify, reinterpret, or supersede higher governance layers unless explicitly authorized through the approved governance process.

The Governance Decision Register (GDR) is **not** a sequential layer within this lifecycle. It functions as a cross-cutting governance-decision, approval, and record-keeping mechanism that applies across every layer of the hierarchy:

```text
                 ┌───────────────────────┐
                 │          GDR          │
                 │  Governance Decisions  │
                 │   Approval / Record    │
                 └───────────┬────────────┘
                              │
                              ▼
   REF → AUTH → GOV → REQ → SOLUTION → CODE → TEST → RELEASE
```

Any normative change to a layer within the lifecycle shall be recorded in the GDR, but the GDR itself does not sit between GOV and REQ or between any two other layers.

---

### GOV-ORG-003 — Rule Authority

**Rule Maturity:** Frozen

Every normative rule implemented within the NSS ERP project shall be traceable to an approved governing authority.

The source of authority shall be one or more of the following:

- Official NSS Bye-Law;
- Authoritative Reference (REF) documents;
- Approved governance standards (AUTH or GOV);
- Approved Governance Decision Register (GDR) entries; or
- Approved project requirements.

Rules without an identifiable governing authority shall not be adopted as project standards.

---

### GOV-ORG-004 — Separation of Governance and Implementation

**Rule Maturity:** Frozen

Project governance establishes **what** shall be governed.

Implementation artifacts define **how** governance requirements are realized.

Governance documents shall not prescribe implementation-specific technologies, architectures, frameworks, programming languages, or deployment strategies unless such implementation choices are themselves approved governance decisions.

This separation ensures governance remains stable while implementation evolves.

---

### GOV-ORG-005 — Traceability Principle

**Rule Maturity:** Frozen

Every project artifact shall maintain traceability to its governing authority.

Traceability shall be preserved across the complete project lifecycle, including:

- governance standards;
- authoritative references;
- requirements;
- solution designs;
- implementation;
- testing; and
- releases.

Loss of traceability shall be treated as a governance non-compliance requiring corrective action.

## 5. Governance Lifecycle

The governance lifecycle defines the processes for establishing, maintaining, modifying, and retiring governance standards within the NSS ERP project.

Governance activities shall preserve stability, traceability, and statutory compliance throughout the project lifecycle.

---

### GOV-LIFE-001 — Governance Baseline

**Rule Maturity:** Frozen

The Governance Baseline establishes the approved set of governance standards that direct the NSS ERP project.

The Governance Baseline shall consist of approved governance documents, including but not limited to:

- AUTH standards;
- GOV standards;
- Governance Decision Register (GDR); and
- other governance documents approved through the governance process.

Routine project development shall operate within the approved Governance Baseline.

---

### GOV-LIFE-002 — Governance Change Control

**Rule Maturity:** Frozen

Changes to approved governance standards shall follow the established governance change control process.

Governance changes include, but are not limited to:

- creation of new governance standards;
- modification of existing governance rules;
- retirement of governance documents;
- restructuring of the governance framework; and
- changes affecting governance authority or traceability.

Normative governance changes shall require approval through the Governance Decision Register (GDR).

---

### GOV-LIFE-003 — Governance Decision Register

**Rule Maturity:** Frozen

The Governance Decision Register (GDR) shall serve as the official record of governance decisions affecting the NSS ERP project.

Each governance decision shall:

- possess a unique identifier;
- record the rationale for the decision;
- identify affected governance documents;
- record approval information; and
- preserve historical traceability.

Approved GDR entries become authoritative governance records.

---

### GOV-LIFE-004 — Governance Version Management

**Rule Maturity:** Frozen

Every governance document shall maintain an explicit version number and revision history.

Version management shall distinguish between:

- editorial revisions;
- governance revisions; and
- baseline revisions.

Governance document versions shall remain permanently traceable throughout the project lifecycle.

Version identifiers shall never be reused or reassigned.

---

### GOV-LIFE-005 — Governance Retirement

**Rule Maturity:** Frozen

Governance documents shall not be permanently deleted once approved.

When a governance document is superseded or withdrawn, it shall be:

- marked with an appropriate status;
- retained within the repository for historical reference;
- linked to its replacement, where applicable; and
- preserved to maintain governance traceability.

Retired governance documents shall remain part of the permanent governance history.

---

### GOV-LIFE-006 — Governance Document Status Lifecycle

**Rule Maturity:** Frozen

Every governance document shall progress through the following Document Status values, recorded in its metadata table:

```text
Draft → Review → Approved → Superseded / Retired
```

- **Draft** — the document is under initial authoring; content may change without governance change control.
- **Review** — the document is undergoing governance review per GOV-ROLE-004.
- **Approved** — the document has completed governance review and forms part of the active Governance Baseline.
- **Superseded / Retired** — the document has been replaced or withdrawn; it is retained per GOV-LIFE-005.

Document Status is independent of Rule Maturity, which is recorded per individual rule, and of Decision Status, which is recorded per individual Governance Decision Register entry (GDR-001).

Transitions between Document Status values shall be recorded in the document's Revision History.

## 6. Governance Roles and Responsibilities

This section defines the governance responsibilities necessary to establish accountability, maintain governance integrity, and ensure compliance throughout the NSS ERP project lifecycle.

---

### GOV-ROLE-001 — Project Owner

**Rule Maturity:** Frozen

The Project Owner is responsible for the overall governance of the NSS ERP project.

Responsibilities include:

- establishing governance objectives;
- approving the Governance Baseline;
- ensuring statutory alignment;
- approving major governance decisions; and
- providing strategic direction for project governance.

The Project Owner serves as the highest authority for project governance, subject to the Official NSS Bye-Law.

The Project Owner is Nilachala Saraswata Sangha (NSS) itself — the ERP project exists to serve NSS, and NSS holds ultimate ownership of its governance, subject to the Official NSS Bye-Law. See GDR-004.

---

### GOV-ROLE-002 — Governance Authority

**Rule Maturity:** Frozen

The Governance Authority is responsible for maintaining the project governance framework.

Responsibilities include:

- reviewing governance proposals;
- maintaining governance standards;
- evaluating Governance Decision Register (GDR) entries;
- ensuring governance consistency;
- preserving traceability; and
- monitoring compliance with approved governance standards.

The Governance Authority shall ensure that governance documentation remains accurate, complete, and internally consistent.

The Governance Authority role is exercised by the Project Steering Committee. This is the body recorded as "Owner" and "Approver" in the metadata of AUTH/GOV/GDR domain documents. See GDR-004.

---

### GOV-ROLE-003 — Contributors

**Rule Maturity:** Frozen

Project contributors shall perform their assigned responsibilities in accordance with approved governance standards.

Contributors shall:

- comply with applicable governance documents;
- maintain traceability for project artifacts;
- follow approved requirements and solution designs;
- document governance impacts when proposing changes; and
- participate in governance reviews when required.

Contributors shall not introduce governance changes outside the approved governance process.

---

### GOV-ROLE-004 — Review and Approval

**Rule Maturity:** Frozen

Governance documents shall undergo appropriate review before approval.

The review process shall verify:

- statutory alignment;
- compliance with governance standards;
- traceability;
- document completeness;
- consistency with existing governance documentation; and
- readiness for approval.

Approval signifies that the document has successfully completed the required governance review process.

---

### GOV-ROLE-005 — Accountability

**Rule Maturity:** Frozen

Governance responsibilities shall be clearly assigned and maintained throughout the project lifecycle.

Each governance activity shall have an identified responsible authority.

Responsibility for governance may be delegated; however, accountability for governance decisions remains with the approving authority.

---

### GOV-ROLE-006 — Final Decision Authority

**Rule Maturity:** Frozen

Final decision authority for governance decisions recorded in the Governance Decision Register (GDR-001) rests with the NSS Governing Body — the statutory governing body of Nilachala Saraswata Sangha (REF-003-C(i)(1)) — exercised through its President (REF-003-C(i)(3)) and/or Parichalak (REF-003-C(i)(8)) in accordance with the Official NSS Bye-Law.

This is distinct from the Governance Authority (GOV-ROLE-002), which maintains and reviews the governance framework day-to-day but does not hold final decision authority over individual governance decisions. The Decision Authority field defined in GDR-001 shall, for this project, be recorded as the NSS Governing Body unless a specific decision is explicitly and formally delegated otherwise.

See GDR-004.

## 7. Governance Compliance

This section establishes the mandatory compliance requirements for all governance activities, project artifacts, and contributors within the NSS ERP project.

Compliance ensures that the project remains consistent with approved governance standards, authoritative references, and the Governance Baseline.

---

### GOV-COMP-001 — Mandatory Compliance

**Rule Maturity:** Frozen

All governance documents, project artifacts, and project activities shall comply with the approved governance framework.

Compliance shall include adherence to:

- Official NSS Bye-Law;
- Authoritative Reference (REF) documents;
- Repository governance standards (AUTH);
- Project governance standards (GOV);
- Approved Governance Decision Register (GDR) entries;
- Approved project requirements; and
- Applicable project standards.

Non-compliant artifacts shall not receive approval.

---

### GOV-COMP-002 — Governance Exceptions

**Rule Maturity:** Frozen

Exceptions to approved governance standards shall be permitted only through an approved Governance Decision Register (GDR) entry.

Each governance exception shall:

- identify the affected governance standard;
- document the business justification;
- identify associated risks;
- define the scope of the exception;
- specify the approval authority; and
- define the duration of the exception, where applicable.

Unapproved governance exceptions shall not be implemented.

---

### GOV-COMP-003 — Governance Review

**Rule Maturity:** Frozen

The governance framework shall be reviewed periodically to ensure continued effectiveness, consistency, and alignment with project objectives.

Governance reviews may evaluate:

- governance completeness;
- statutory alignment;
- traceability;
- document consistency;
- governance process effectiveness; and
- opportunities for continuous improvement.

Governance reviews shall not modify the Governance Baseline unless approved through the governance change control process.

---

### GOV-COMP-004 — Corrective Actions

**Rule Maturity:** Frozen

Governance non-compliance shall require appropriate corrective action.

Corrective actions may include:

- document revision;
- traceability correction;
- governance review;
- implementation correction;
- additional verification; or
- governance approval through the established change process.

Corrective actions shall preserve governance integrity and historical traceability.

---

### GOV-COMP-005 — Governance Baseline Protection

**Rule Maturity:** Frozen

The Governance Baseline shall remain protected from uncontrolled modification.

Routine project development shall operate within the approved baseline.

Changes to the Governance Baseline shall require:

- governance review;
- Governance Decision Register (GDR) approval;
- revision of affected governance standards; and
- preservation of governance traceability.

The Governance Baseline is a governed project asset and shall remain under formal governance control.

## Appendix A — Governance Lifecycle

```text
Official Constitution & Bye-Laws
            │
            ▼
           REF
            │
            ▼
          AUTH
            │
            ▼
           GOV
            │
            ▼
           REQ
            │
            ▼
       SOLUTION
            │
            ▼
          CODE
            │
            ▼
          TEST
            │
            ▼
        RELEASE
```

The Governance Decision Register (GDR) is a cross-cutting mechanism applied across all layers of this lifecycle. It is not a sequential layer and does not sit between any two layers shown above.

This appendix is informative.

The normative governance hierarchy is defined in GOV-ORG-002.

## Appendix B — Document Hierarchy

| Layer | Primary Purpose |
|--------|-----------------|
| Constitution | Highest governing authority |
| REF | Statutory references |
| AUTH | Repository governance |
| GOV | Project governance |
| REQ | Business requirements |
| SOLUTION | Technical solution design |
| CODE | Software implementation |
| TEST | Verification and validation |
| RELEASE | Approved project releases |
| GDR | Governance decisions (cross-cutting; applies across all layers above, not positioned sequentially between them) |

This appendix is informative.

## Appendix C — Governance Responsibility Matrix

| Activity | Project Owner | Governance Authority | Contributors |
|----------|---------------|----------------------|--------------|
| Governance Standards | Approve | Maintain | Contribute |
| Governance Decisions | Approve | Review | Propose |
| Requirements | Approve | Review | Develop |
| Solution Design | Review | Review | Develop |
| Implementation | Monitor | Review | Implement |
| Testing | Monitor | Review | Execute |
| Releases | Approve | Verify | Support |

This appendix is informative.

# End of Document
