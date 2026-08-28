# NSS ERP Master Data Catalog

Version: 1.0

Status: FROZEN

---

# 1. Purpose

This document defines all configurable master data used throughout NSS ERP.

Business logic shall reference master tables rather than hardcoded values.

---

# 2. Master Data Principles

Configuration Over Hardcoding

Master Data Driven

By-Law Aligned

Expandable Without Code Changes

Auditable

---

# 3. Geography Masters

## country_master

Examples:

INDIA

---

## state_master

Examples:

ODISHA

WEST_BENGAL

ASSAM

---

## district_master

Examples:

KHORDHA

CUTTACK

PURI

GANJAM

---

# 4. Organization Masters

## organization_type_master

Values:

KENDRA

ANCHALIKA

ZILLA

SAKHA

PATHA_CHAKRA

---

## organization_status_master

Values:

ACTIVE

INACTIVE

DISSOLVED

UNDER_FORMATION

---

# 5. Membership Masters

## membership_type_master

Values:

PROBATIONARY

REGULAR

ASSOCIATE

HONORARY

---

## membership_status_master

Values:

ACTIVE

SUSPENDED

CANCELLED

DECEASED

TRANSFERRED

---

## membership_renewal_status_master

Values:

PENDING

RENEWED

EXPIRED

REJECTED

---

# 6. Family Masters

## relationship_type_master

Values:

FATHER

MOTHER

SON

DAUGHTER

HUSBAND

WIFE

BROTHER

SISTER

GUARDIAN

OTHER

---

## family_status_master

Values:

ACTIVE

INACTIVE

MERGED

CLOSED

---

# 7. Governance Masters

## body_type_master

Values:

GENERAL_BODY

GOVERNING_BODY

ADVISORY_BOARD

MAHILA_PARICHALANA_MANDALI

COMMITTEE

---

## position_master

Examples:

PRESIDENT

VICE_PRESIDENT

SECRETARY

ASSISTANT_SECRETARY

TREASURER

MEMBER

ADVISOR

---

## position_status_master

Values:

ACTIVE

VACANT

ACTING

COMPLETED

---

# 8. Attendance Masters

## attendance_status_master

Values:

PRESENT

ABSENT

EXCUSED

---

## attendance_review_status_master

Values:

OPEN

DEFERRED

CLOSED

ESCALATED

---

# 9. Security Masters

## role_master

Examples:

SYSTEM_ADMINISTRATOR

KENDRA_ADMINISTRATOR

PARICHALAK

PRESIDENT

SECRETARY

TREASURER

MEMBER

---

## permission_master

Permission records managed by system.

Examples:

person.view

person.create

membership.approve

attendance.review

governance.assign

---

## scope_master

Values:

KENDRA

ANCHALIKA

ZILLA

SAKHA

PERSONAL

---

# 10. Application Workflow Masters

## application_type_master

Examples:

MEMBERSHIP_APPLICATION

TRANSFER_REQUEST

RENEWAL_REQUEST

ATTENDANCE_APPEAL

---

## application_status_master

Values:

DRAFT

SUBMITTED

UNDER_REVIEW

APPROVED

REJECTED

CLOSED

---

# 11. Approval Workflow Masters

## approval_status_master

Values:

PENDING

APPROVED

REJECTED

RETURNED

---

## approval_action_master

Values:

APPROVE

REJECT

RETURN

ESCALATE

---

# 12. Heritage Masters

## publication_type_master

Values:

BOOK

MAGAZINE

JOURNAL

NEWSLETTER

ANNUAL_REPORT

UPBS_SOUVENIR

PAMPHLET

OTHER

---

## publication_language_master

Values:

ODIA

ENGLISH

HINDI

BENGALI

ASSAMESE

TELUGU

TAMIL

OTHER

---

# 13. Kumari Masters

## kumari_status_master

Values:

ACTIVE

INACTIVE

COMPLETED

WITHDRAWN

---

# 14. Kishor Masters

## kishor_status_master

Values:

ACTIVE

INACTIVE

COMPLETED

WITHDRAWN

---

# 15. Sevak Masters

## seva_role_master

Values:

SEVA_HEAD

SEVA_CO_HEAD

SEVA_MEMBER

SEVA_VOLUNTEER

---

# 16. UPBS Masters

## event_type_master

Values:

UPBS

JANMOSCHABA

ZILLA_PUJA

ANCHALIKA_PUJA

SPECIAL_EVENT

---

## event_session_master

Values:

ADHIBASA

DAY_1

DAY_2

DAY_3

---

## meal_type_master

Values:

BREAKFAST

LUNCH

DINNER

---

# 17. Finance Masters

## currency_master

Values:

INR

---

## financial_year_master

Examples:

FY2025

FY2026

FY2027

---

# 18. System Masters

## yes_no_master

Values:

YES

NO

---

## active_inactive_master

Values:

ACTIVE

INACTIVE

---

# 19. Future Expansion Rule

New master tables may be added without modifying existing business tables whenever possible.

---

# 20. Master Data Principles Summary

No Hardcoded Business Values

Use Master Tables

Use Foreign Keys

Support Future Growth

Preserve History

Keep Configuration Centralized
