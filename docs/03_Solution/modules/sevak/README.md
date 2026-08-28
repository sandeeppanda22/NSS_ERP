# NSS ERP Sevak Sangha Module

Status: DRAFT (consolidation in progress) — only the table design is Frozen. Sevak Sangha
remains only **partially frozen** per `CLAUDE.md` §7/§10: foundation exists but executive
structure, formal training hierarchy, and full operational lifecycle are still incomplete. There
is still no `backend/sevak/` Django app.

---

## Documents

```
01_sevak_module_overview.md       SOL-SEV-001,      v2.0.0  DRAFT — consolidation in progress
02_sevak_erd.md                   SOL-SEV-002,      v2.0.0  DRAFT — consolidation in progress
03_sevak_lifecycle.md             SOL-SEV-003,      v2.0.0  DRAFT — consolidation in progress
04_sevak_participation_rules.md   SOL-SEV-PART-001, v1.0.0  DRAFT — consolidation in progress
05_sevak_business_rules.md        SOL-SEV-004,      v6.0.0  DRAFT — consolidation in progress
06_sevak_table_design.md          SOL-SEV-005,      v2.0.0  FROZEN FOUNDATION / IMPLEMENTATION READY
sangha/01_sakha_sevak_sangha_session_rules.md         SOL-SEV-SANGHA-001, v1.0.0  DRAFT
sangha/02_anchalika_zilla_sevak_sangha_puja_rules.md  SOL-SEV-SANGHA-002, v1.0.0  DRAFT
seva/01_seva_business_rules.md                        SOL-SEV-SEVA-001,   v1.0.0  DRAFT
seva/02_upbs_seva_rules.md                             SOL-SEV-SEVA-002,   v1.0.0  DRAFT
events/01_other_sevak_event_rules.md                   SOL-SEV-EVENT-001,  v1.0.0  DRAFT
```

`05_sevak_business_rules.md` is the consolidated core rule set, numbering `SEV-001`–`SEV-040`
(the domain-specific `sangha/`, `seva/`, `events/` sub-documents use plain numbered sections, not
`SEV-XXX` IDs). An earlier freeze commit referenced "SEV-013 through SEV-048" — that applied to
the pre-restructure monolithic file; the subsequent split/renumber consolidated the core set down
to 001–040, with an explicit note (§22) that source ID collisions (duplicate SEV-024, SEV-025,
SEV-032) were found and deliberately not silently patched.

---

## Genuinely open gaps (per `01_sevak_module_overview.md` §39/§59 and `05_sevak_business_rules.md`
§14/§15)

- Executive/governance structure (positions, selection/election, term duration) — only a
  provisional body type (`SEVAK_SANGHA_EXECUTIVE`) exists so far.
- No formal/mandatory training hierarchy.
- No Kishor → Sevak automatic transition rule.
- Membership lifecycle and full operational structure still incomplete.

---

## Current Status

Design Complete · ERD Complete · Lifecycle/Participation/Business Rules Drafted (consolidation
in progress, not Frozen) · Table Design Frozen (implementation-ready) · SQL Implementation Not
Started · `backend/sevak/` Django app does not exist yet
