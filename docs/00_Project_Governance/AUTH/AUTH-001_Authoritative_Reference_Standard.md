# AUTH-001 — Authoritative Reference Standard

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Authoritative Reference Standard |
| Document ID | AUTH-001 |
| Domain | AUTH |
| Repository Path | docs/00_Project_Governance/AUTH/ |
| Version | 1.1.0 |
| Status | Approved |
| Governance Baseline | v1.0 |
| Authority | NSS ERP Governance Framework |
| Owner | NSS ERP Project |
| Effective Date | TBD |

---

## Revision History

| Version | Date | Description |
|---|---|---|
| 1.0.0 | TBD | Initial draft created following Governance Baseline v1.0 |
| 1.1.0 | 2026-08-13 | Renamed per-rule `Status` field to `Rule Maturity` to disambiguate from document-level Status (see GOV-001 GOV-LIFE-006); Status advanced from Draft to Approved to reflect actual governance use. See GDR-003. |

---

## Table of Contents

1. Purpose
2. Scope
3. Definitions
4. Governance Context
5. Repository Architecture
6. Authoritative Reference Repository Standard
7. Authoritative Reference Identification Standard
8. Repository Metadata Standard
9. Repository Cross-Reference Standard
10. Repository Traceability Standard
11. Repository Verification Standard
12. Repository Governance and Lifecycle
13. Compliance Requirements

Appendix A – Repository Structure
Appendix B – REF Family Mapping
Appendix C – File Naming Examples
Appendix D – REF Metadata Template
Appendix E – Traceability Examples
Appendix F – Editorial vs. Normative Change Examples

End of Document

---

## 1. Purpose

This standard establishes the authoritative rules governing the organization, identification, management, verification, and traceability of the Authoritative Reference (REF) repository within the NSS ERP project.

Its purpose is to ensure that all authoritative reference documents are managed in a consistent, traceable, and maintainable manner while preserving the integrity of the official constitutional and governing documents from which they are derived.

This standard governs the repository that contains authoritative references. It does not replace, reinterpret, or supersede the official governing documents.

---

## 2. Scope

This standard applies to all Authoritative Reference (REF) documents maintained within the NSS ERP project.

It defines the standards for:

- Repository organization.
- Document identification.
- Metadata.
- Cross-references.
- Traceability.
- Verification.
- Version management.
- Governance of repository changes.

This standard does not define constitutional provisions, business rules, functional requirements, implementation details, or software design.

---

## 3. Definitions

For the purposes of this standard:

**Authoritative Reference (REF)**

A repository document that faithfully represents and references an official governing source without altering its meaning.

**Official Governing Document**

A constitution, bye-law, resolution, notification, circular, or other document formally recognized by the NSS governance structure.

**Repository**

The managed collection of Authoritative Reference documents maintained by the NSS ERP project.

**Normative Rule**

A mandatory requirement expressed within this standard.

**Editorial Content**

Supporting material such as metadata, introductions, examples, notes, or formatting that does not alter the meaning of an authoritative source.

**Rule Maturity**

An attribute recorded on an individual normative rule within this standard (e.g. `Frozen`), indicating whether that specific rule's content may be modified without governance change control. Rule Maturity is distinct from Document Status — the approval-lifecycle state of the document as a whole, defined in GOV-001 (GOV-LIFE-006).

---

## 4. Governance Context

The NSS ERP project follows the Governance Baseline v1.0 lifecycle:

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

---

## 5. Repository Architecture

This section establishes the authoritative repository architecture for governance and documentation within the NSS ERP project.

The repository architecture is governed by the following normative rules.

---

### AUTH-ORG-001 — Governance Repository Structure

**Rule Maturity:** Frozen

The NSS ERP documentation repository shall be organized into governance domains that reflect the Governance Baseline v1.0 lifecycle.

The top-level documentation structure shall be:

```text
docs/
│
├──00_Project_Governance/
│   ├──AUTH/
│   ├──GOV/
│   └──GDR/
│
├──01_Authoritative_References/
│
├──02_Requirements/
│
├──03_Solution/
│
├──04_Testing/
│
└──05_Releases/
```

No additional top-level documentation domains shall be introduced without approval through the Governance Decision Register (GDR).

---

### AUTH-ORG-002 — Domain Responsibilities

**Rule Maturity:** Frozen

Each documentation domain has a single defined responsibility.

| Domain | Responsibility |
|---------|----------------|
| AUTH | Standards governing the Authoritative Reference repository |
| GOV | Governance principles and standards |
| GDR | Governance decisions and architectural change history |
| REF | Authoritative constitutional references |
| REQ | Business and functional requirements |
| SOLUTION | Architecture and technical design |
| TEST | Verification and validation |
| RELEASE | Versioned release documentation |

A document shall belong to exactly one primary documentation domain.

---

### AUTH-ORG-003 — Repository Layer Independence

**Rule Maturity:** Frozen

Each documentation layer shall remain independent in purpose and responsibility.

A higher layer may govern a lower layer, but a lower layer shall not redefine or supersede a higher layer.

The governance hierarchy is:

```text
REF
    ↓
AUTH
    ↓
GOV
    ↓
REQ
    ↓
SOLUTION
    ↓
CODE
    ↓
TEST
    ↓
RELEASE
```

---

### AUTH-ORG-004 — Repository Organization Principle

**Rule Maturity:** Frozen

Repository folders exist solely for organization and navigation.

Repository folder names shall not constitute authoritative identifiers.

Permanent document identity shall be established only through document identifiers defined by the applicable documentation standard.

---

### AUTH-ORG-005 — Repository Extensibility

**Rule Maturity:** Frozen

The repository architecture is designed to support future expansion.

New documents may be added within existing documentation domains without modifying the governance baseline.

Creation of a new documentation domain or modification of the governance lifecycle constitutes a normative governance change and shall follow the Governance Decision Register (GDR) process.

---

## 6. Authoritative Reference Repository Standard

This section establishes the standards governing the organization of the Authoritative Reference (REF) repository.

The REF repository contains the constitutional source documents upon which all downstream governance, requirements, solution artifacts, implementation, testing, and releases are based.

---

### AUTH-REF-001 — Constitutional Source Repository

**Rule Maturity:** Frozen

The Authoritative Reference (REF) repository is the constitutional source repository of the NSS ERP project.

The REF repository shall contain only documents derived directly from officially recognized governing sources.

Where no authoritative governing source exists, downstream artifacts shall explicitly identify their content as implementation decisions.

---

### AUTH-REF-002 — Repository Organization

**Rule Maturity:** Frozen

The REF repository shall be organized according to the official constitutional hierarchy.

Repository organization shall preserve the official structure of the governing documents.

Editorial convenience shall never supersede constitutional organization.

---

### AUTH-REF-003 — Repository Hierarchy

**Rule Maturity:** Frozen

The REF repository shall organize governing documents into recognized document families.

The initial repository hierarchy shall include:

```text
01_Authoritative_References/
│
├──NSS/
│
├──MAHILA_SANGHA/
│
├──RESOLUTIONS/
│
├──CIRCULARS/
│
└──NOTIFICATIONS/
```

Additional document families may be introduced only when officially recognized governing documents exist.

---

### AUTH-REF-004 — Constitutional Integrity

**Rule Maturity:** Frozen

Repository organization shall preserve:

- official section numbering
- official lettering
- official hierarchy
- official ordering

The repository shall not introduce alternative constitutional structures.

---

### AUTH-REF-005 — Editorial Separation

**Rule Maturity:** Frozen

Editorial material may accompany authoritative references for repository management purposes.

Editorial material shall be clearly distinguishable from authoritative constitutional text.

Editorial content shall never alter, reinterpret, or supersede the meaning of the governing source.

---

## 7. Authoritative Reference Identification Standard

This section establishes the permanent identification standard for all Authoritative Reference (REF) documents.

Document identifiers are immutable and provide the primary means of identifying, tracing, and referencing authoritative documents throughout the NSS ERP project.

---

### AUTH-ID-001 — Permanent Document Identity

**Rule Maturity:** Frozen

Every Authoritative Reference (REF) document shall have a permanent document identifier.

Once assigned, a document identifier shall never be reused, reassigned, or renumbered.

Deprecation of a document shall not invalidate or recycle its identifier.

---

### AUTH-ID-002 — REF Family Assignment

**Rule Maturity:** Frozen

Each REF document shall belong to exactly one REF family.

A REF family corresponds to one or more officially recognized governing document sections grouped under a single family identifier. A REF family may cover a single section (e.g. `REF-001` for Section A) or multiple contiguous sections of the same governing document (e.g. `REF-003`, which covers Sections C through I of the NSS Bye-Law), provided the composite document identifier (AUTH-ID-003) preserves the official section lettering needed to uniquely distinguish every document within that family.

The current REF family assignments for the NSS Bye-Law are recorded in Appendix B.

The mapping between a REF family and its governing document section(s), once assigned, is permanent. See AUTH-ID-002A for the process governing creation of new REF families for other governing entities.

---

### AUTH-ID-002A — New REF Family Creation

**Rule Maturity:** Frozen

The numbered `REF-00X` family (REF-001 through REF-010, or as extended within that numbering scheme) is reserved exclusively for sections of the Nilachala Saraswata Sangha's own official governing document (the Kendra Sangha Bye-Law).

A **separate, dedicated REF family** shall be created — rather than extending the `REF-00X` numbering — whenever authoritative reference material originates from a **distinct, separately registered governing entity** with its own official governing document, rather than from a section of the NSS Bye-Law itself.

Each such dedicated family shall:

- Use a short, stable alphabetic family code reflecting the governing entity (e.g. `REF-MS` for the Nilachala Saraswata Mahila Sangha);
- Be documented in Appendix B of this standard at the time of creation;
- Follow the same identification, metadata, cross-reference, traceability, and verification standards defined elsewhere in this document as any other REF family;
- Preserve the source document's own clause numbering as its composite locator (see AUTH-ID-003), exactly as required for the `REF-00X` family.

Creation of a new REF family is a normative change to this standard and shall follow the Governance Decision Register (GDR) process defined in AUTH-GOV-002.

Example: `REF-MS` was created for the Constitution & Bye-Laws of the Nilachala Saraswata Mahila Sangha — a registered entity operating under, and subordinate to, the Nilachala Saraswata Sangha, but governed by its own separate Bye-Law rather than by a section of the NSS Bye-Law. See GDR-002.

---

### AUTH-ID-003 — Composite Document Identifier

**Rule Maturity:** Frozen

Each REF document identifier shall consist of:

- REF Family Identifier
- Official Constitutional Reference

Example:

```text
REF-001-A

REF-003-C(i)(2)

REF-003-F[A]
```

The official constitutional reference shall preserve the official numbering, lettering, punctuation, and hierarchy exactly as published in the governing document.

---

### AUTH-ID-004 — File Naming Convention

**Rule Maturity:** Frozen

The repository filename shall include:

- Composite REF Identifier
- Human-readable title

General format:

```text
<Composite Identifier>_<Document Title>.md
```

Example:

```text
REF-003-C(i)(2)_Functions_of_the_Governing_Body.md

REF-003-F[b]_Maintenance_of_the_Funds.md
```

The filename exists for repository readability.

The document identifier remains the authoritative identity.

---

### AUTH-ID-005 — Identifier Independence

**Rule Maturity:** Frozen

Document identity shall not depend upon:

- repository folder
- file location
- repository URL
- branch name
- operating system path

Only the assigned document identifier constitutes the permanent identity of a REF document.

Repository organization may evolve without affecting document identity.

---

## 8. Repository Metadata Standard

This section establishes the mandatory metadata requirements for all Authoritative Reference (REF) documents.

Metadata provides document identity, governance status, traceability, and repository management information. Metadata forms part of the repository management layer and shall not alter the meaning of the authoritative constitutional text.

---

### AUTH-META-001 — Mandatory Metadata

**Rule Maturity:** Frozen

Every REF document shall contain a metadata section before the document content.

The metadata section shall be complete before a document is approved.

---

### AUTH-META-002 — Standard Metadata Fields

**Rule Maturity:** Frozen

Every REF document shall contain the following metadata.

| Field | Description |
|--------|-------------|
| Document Name | Official repository document name |
| Document ID | Permanent REF identifier |
| REF Family | Associated REF family |
| Official Reference | Constitutional or Bye-Law reference |
| Repository Path | Repository location |
| Source Document | Official governing document |
| Version | Repository document version |
| Status | Draft, Review, Approved, Deprecated |
| Authority | Governing authority |
| Owner | Repository owner |
| Effective Date | Date the repository version becomes effective |
| Last Updated | Date of most recent revision |

Additional metadata fields may be introduced through the governance change process.

---

### AUTH-META-003 — Metadata Integrity

**Rule Maturity:** Frozen

Metadata shall accurately describe the associated REF document.

Metadata shall never:

- modify constitutional meaning
- reinterpret governing text
- introduce new business rules

Metadata exists solely for repository governance and management.

---

### AUTH-META-004 — Metadata Consistency

**Rule Maturity:** Frozen

Metadata field names shall be standardized across all REF documents.

Equivalent metadata shall use identical field names and formatting throughout the repository.

Alternative labels shall not be introduced without governance approval.

---

### AUTH-META-005 — Metadata Versioning

**Rule Maturity:** Frozen

Changes to metadata shall follow repository version management.

Editorial updates may modify metadata without affecting constitutional content.

Normative metadata changes that alter repository governance shall follow the Governance Decision Register (GDR) process.

---

### AUTH-META-006 — Metadata Placement

**Rule Maturity:** Frozen

The metadata section shall appear immediately after the document title and before all other document content.

The recommended document order is:

1. Document Title
2. Metadata
3. Revision History
4. Table of Contents
5. Normative Content
6. Appendices (if applicable)

This structure shall be applied consistently across all REF documents.

---

## 9. Repository Cross-Reference Standard

This section establishes the standards governing cross-references between Authoritative Reference (REF) documents and between REF documents and downstream project artifacts.

Cross-references provide navigational and traceability support. They shall not modify or reinterpret the meaning of the referenced authoritative source.

---

### AUTH-XREF-001 — Standard Cross References

**Rule Maturity:** Frozen

Cross-references shall use permanent document identifiers.

Repository paths, folder names, file locations, and URLs shall not be used as permanent references.

Example:

```
Correct

REF-003-C(2)

Incorrect

docs/01_Authoritative_References/...
```

---

### AUTH-XREF-002 — Reference Format

**Rule Maturity:** Frozen

Where applicable, a cross-reference shall include:

- REF Document Identifier
- Official Constitutional Reference
- Document Title (optional)

Example:

```
REF-003-C(2)
Section C(2)
Functions of the Governing Body
```

The document identifier remains the authoritative reference.

---

### AUTH-XREF-003 — Cross-Layer References

**Rule Maturity:** Frozen

Downstream documentation shall reference higher governance layers.

Examples include:

```
REQ → GOV
REQ → REF

SOLUTION → REQ

TEST → REQ

RELEASE → SOLUTION
RELEASE → TEST
```

Cross-layer references shall preserve end-to-end traceability.

---

### AUTH-XREF-004 — Broken References

**Rule Maturity:** Frozen

Published documents shall not contain broken cross-references.

Repository validation shall verify that all referenced document identifiers exist and remain valid.

Deprecated documents shall remain referenceable through their permanent identifiers.

---

### AUTH-XREF-005 — Reference Stability

**Rule Maturity:** Frozen

Repository restructuring, folder renaming, or file relocation shall not invalidate document references.

Cross-references shall remain stable through the use of permanent document identifiers.

Only the referenced document identifier constitutes the authoritative target.

---

## 10. Repository Traceability Standard

This section establishes the mandatory traceability requirements for all Authoritative Reference (REF) documents and their relationship to downstream governance, requirements, solution, implementation, testing, and release artifacts.

Traceability ensures that every project artifact can be traced to its governing authority or be explicitly identified as an implementation decision.

---

### AUTH-TRACE-001 — End-to-End Traceability

**Rule Maturity:** Frozen

The NSS ERP project shall maintain end-to-end traceability throughout the governance lifecycle.

The authoritative traceability chain is:

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

Each downstream layer shall maintain traceability to the layer from which it derives its authority.

---

### AUTH-TRACE-002 — Constitutional Authority

**Rule Maturity:** Frozen

Every business rule implemented within the NSS ERP project shall originate from:

- an Authoritative Reference (REF), or
- an approved governance standard (GOV), or
- an explicitly documented implementation decision where no authoritative source exists.

Implementation decisions shall be clearly identified and shall not be presented as constitutional requirements.

---

### AUTH-TRACE-003 — Downstream Traceability

**Rule Maturity:** Frozen

Each documentation layer shall maintain traceability to its immediate governing layer.

| Artifact | Shall Trace To |
|----------|----------------|
| AUTH | REF |
| GOV | AUTH and REF |
| REQ | GOV and REF |
| SOLUTION | REQ |
| CODE | SOLUTION |
| TEST | REQ and CODE |
| RELEASE | SOLUTION, CODE, and TEST |

Additional traceability may be maintained where beneficial.

---

### AUTH-TRACE-004 — Traceability Preservation

**Rule Maturity:** Frozen

Traceability links shall be preserved throughout the lifecycle of a document.

Repository reorganization, document relocation, or editorial revisions shall not invalidate existing traceability.

Permanent document identifiers shall be used to preserve traceability.

---

### AUTH-TRACE-005 — Missing Authority

**Rule Maturity:** Frozen

Where no authoritative constitutional or governance source exists for a requirement or solution, the artifact shall explicitly identify the content as an implementation decision.

Implementation decisions shall not be represented as constitutional authority.

---

### AUTH-TRACE-006 — Traceability Validation

**Rule Maturity:** Frozen

Traceability shall be verified before approval of any published artifact.

Verification shall confirm:

- all required traceability links exist;
- referenced identifiers are valid;
- governing authority is correctly identified; and
- implementation decisions are explicitly marked where applicable.

---

## 11. Repository Verification Standard

This section establishes the mandatory verification requirements for all Authoritative Reference (REF) documents.

Verification ensures that every REF document accurately represents its authoritative source and complies with the standards defined in AUTH-001 before publication or approval.

---

### AUTH-VERIFY-001 — Mandatory Verification

**Rule Maturity:** Frozen

Every REF document shall undergo verification before being assigned the status **Approved**.

No REF document shall be published as an approved authoritative reference without successful verification.

---

### AUTH-VERIFY-002 — Verification Scope

**Rule Maturity:** Frozen

Verification shall confirm, at a minimum:

- Document identifier
- Official constitutional reference
- Repository location
- Metadata completeness
- Cross-reference integrity
- Traceability compliance
- Repository naming standards
- Constitutional text accuracy

Additional verification criteria may be introduced through governance approval.

---

### AUTH-VERIFY-003 — Constitutional Accuracy

**Rule Maturity:** Frozen

The authoritative constitutional text contained within a REF document shall accurately reflect the officially approved governing source.

Verification shall confirm:

- Section numbering
- Clause numbering
- Lettering
- Ordering
- Constitutional wording

Editorial content shall be excluded from constitutional verification except where it affects document integrity.

---

### AUTH-VERIFY-004 — Repository Compliance

**Rule Maturity:** Frozen

Verification shall confirm compliance with all applicable AUTH standards, including:

- Repository organization
- Document identification
- Metadata
- Cross-references
- Traceability
- Version management

Non-compliant documents shall not receive Approved status.

---

### AUTH-VERIFY-005 — Verification Record

**Rule Maturity:** Frozen

Verification activities shall be recorded as part of the document revision history or other approved repository governance mechanism.

Verification records shall identify:

- Verification date
- Document version
- Verification outcome
- Reviewer (where applicable)

Verification records form part of the repository governance history.

---

### AUTH-VERIFY-006 — Reverification

**Rule Maturity:** Frozen

A previously approved REF document shall be reverified whenever:

- Constitutional content changes
- Repository metadata is materially modified
- Document identifiers are corrected
- Traceability is updated
- Governance standards affecting the document are revised

Editorial corrections that do not affect governance, traceability, or constitutional integrity may be exempt from full reverification.

---

## 12. Repository Governance and Lifecycle

This section establishes the governance requirements for managing the Authoritative Reference (REF) repository throughout its lifecycle.

It defines version management, governance change control, editorial practices, and compliance responsibilities.

---

### AUTH-GOV-001 — Repository Version Management

**Rule Maturity:** Frozen

Each AUTH standard shall maintain an explicit version number.

Version numbers shall reflect governance evolution and shall be recorded in the document revision history.

Version identifiers shall never be reused.

---

### AUTH-GOV-002 — Governance Change Control

**Rule Maturity:** Frozen

Normative changes to this standard shall follow the Governance Decision Register (GDR) process.

A normative change includes, but is not limited to:

- addition of new governance rules;
- modification of existing governance rules;
- removal or deprecation of governance rules;
- changes to repository architecture;
- changes to document identification standards; or
- changes affecting traceability or governance responsibilities.

No normative change shall be incorporated without an approved GDR entry.

---

### AUTH-GOV-003 — Editorial Changes

**Rule Maturity:** Frozen

Editorial changes are permitted without modifying the Governance Baseline.

Editorial changes include:

- spelling corrections;
- grammar improvements;
- formatting;
- examples;
- clarifications that do not alter the meaning or intent of a governance rule.

Editorial changes shall not modify normative requirements.

---

### AUTH-GOV-004 — Governance Compliance

**Rule Maturity:** Frozen

All REF documents shall comply with the standards established in AUTH-001.

Non-compliant documents shall be corrected before receiving Approved status.

Compliance verification shall form part of repository governance.

---

### AUTH-GOV-005 — Governance Baseline

**Rule Maturity:** Frozen

Governance Baseline v1.0 establishes the authoritative governance framework for the NSS ERP project.

Routine repository development shall operate within this baseline.

Changes to the governance baseline itself shall require:

- Governance review;
- Governance Decision Register (GDR) approval;
- revision of affected governance standards; and
- preservation of traceability.

The governance baseline is a governed asset and shall not be modified through ordinary feature development.

---

## 13. Compliance Requirements

The standards defined within AUTH-001 are mandatory for all Authoritative Reference (REF) documents maintained by the NSS ERP project.

Repository contributors shall ensure that all documents:

- comply with the repository architecture;
- use approved document identifiers;
- contain complete metadata;
- preserve constitutional integrity;
- maintain traceability;
- satisfy verification requirements; and
- comply with governance change control.

Failure to comply with this standard shall require corrective action before approval.

This standard shall remain in effect until superseded through the established governance process.

---

## Appendix A — Repository Structure

The NSS ERP documentation repository is organized as follows:

```text
docs/
│
├──00_Project_Governance/
│   ├──AUTH/
│   ├──GOV/
│   └──GDR/
│
├──01_Authoritative_References/
│   ├──NSS/
│   ├──MAHILA_SANGHA/
│   ├──RESOLUTIONS/
│   ├──CIRCULARS/
│   └──NOTIFICATIONS/
│
├──02_Requirements/
│
├──03_Solution/
│
├──04_Testing/
│
└──05_Releases/
```

This appendix is informative.

The normative repository architecture is defined by AUTH-ORG-001.

---

## Appendix B — REF Family Mapping

| REF Family | Governing Section(s) | Notes |
|------------|-----------------------|-------|
| REF-001 | Section A | Single section |
| REF-002 | Section B | Single section |
| REF-003 | Sections C through I | Composite locator (AUTH-ID-003) distinguishes documents within Sections C–I: `C(i)(1)`–`C(i)(8)` for the Governing Body sub-clauses, `D`, `E`, `F[A]`, `F[b]`, `F[c]`, `G`, `H`, `I` |

| REF Family | Governing Entity | Governing Document |
|------------|-------------------|---------------------|
| REF-MS | Nilachala Saraswata Mahila Sangha | Bye-Law of Nilachala Saraswata Mahila Sangha (separately registered entity, subordinate to NSS; not a section of the NSS Bye-Law) |

This appendix is informative.

The normative document identification rules are defined in Section 7 (including AUTH-ID-002A, governing creation of new REF families such as REF-MS).

---

## Appendix C — File Naming Examples

Examples (actual repository filenames):

```text
REF-001_NSS_CONSTITUTION.md

REF-002_NSS_MEMBERSHIP_BYLAWS.md

REF-003-C_Constitution_of_the_Kendra_Sangha.md

REF-003-C(i)(1)_Constitution_of_the_Governing_Body.md

REF-003-C(i)(2)_Functions_of_the_Governing_Body.md

REF-003-C(i)(3)_Duties_of_the_President.md

REF-003-D_Advisory_Board.md

REF-003-E_General_Body.md

REF-003-F[A]_Funds_of_the_Kendra_Sangha.md

REF-003-F[b]_Maintenance_of_the_Funds.md

REF-003-F[c]_Utilisation_of_the_Funds.md

REF-003-G_Audit.md

REF-003-H_Power_to_Amend.md

REF-003-I_Dissolution.md
```

These examples illustrate the naming convention.

The normative naming rules are defined in Section 7 (AUTH-ID-004).

---

## Appendix D — REF Metadata Template

Every REF document should use the following metadata template.

| Field | Value |
|--------|-------|
| Document Name | |
| Document ID | |
| REF Family | |
| Official Reference | |
| Repository Path | |
| Source Document | |
| Version | |
| Status | |
| Authority | |
| Owner | |
| Effective Date | |
| Last Updated | |

This appendix provides a standard template.

The normative metadata requirements are defined in Section 8.

---

## Appendix E — Traceability Examples

Example 1

```text
REF-003-C(2)
        │
        ▼
GOV-ORG-005
        │
        ▼
REQ-MEMBER-004
        │
        ▼
SOL-DB-012
        │
        ▼
CODE
        │
        ▼
TEST-MEMBER-008
        │
        ▼
Release v1.2.0
```

This appendix illustrates end-to-end traceability.

The normative traceability requirements are defined in Section 10.

---

## Appendix F — Editorial vs. Normative Change Examples

Examples of Editorial Changes

- Grammar corrections
- Typographical corrections
- Formatting improvements
- Clarifying examples
- Updated revision history

Examples of Normative Changes

- New AUTH rule
- Modified governance rule
- Repository restructuring
- New metadata requirement
- Identifier format changes
- Traceability rule changes

Normative changes require Governance Decision Register (GDR) approval.

This appendix is illustrative.

The normative governance requirements are defined in Section 12.

---

# End of Document
