# NSS ERP Security Standards

Version: 1.0

Status: FROZEN

---

# 1. Purpose

This document defines the security architecture, access control model, authentication standards, authorization rules, and data protection requirements for NSS ERP.

Security shall be designed into the system from the beginning.

---

# 2. Security Principles

Principle of Least Privilege

Role-Based Access Control

Defense in Depth

Auditability

Data Privacy

Secure by Default

No Anonymous Access

---

# 3. Authentication Model

Users must authenticate before accessing NSS ERP.

Authentication methods:

Username + Password

Future:

OTP

MFA

SSO

---

# 4. User Identity Model

A user account may be linked to:

Sangha Sevi

Office Bearer

Administrator

System Operator

Every user account must have a unique identity.

---

# 5. Password Standards

Minimum Length:

12 characters

Must contain:

Uppercase Letter

Lowercase Letter

Number

Special Character

Passwords shall never be stored in plain text.

---

# 6. Password Storage

Approved:

Argon2

Fallback:

PBKDF2

Prohibited:

MD5

SHA1

Plain Text

Reversible Encryption

---

# 7. Account Lock Policy

Lock after:

5 consecutive failed login attempts

Default lock duration:

30 minutes

Administrative unlock supported.

---

# 8. Session Management

Automatic logout:

30 minutes inactivity

Force logout after password reset.

Terminate all sessions after account lock.

---

# 9. Role Based Access Control (RBAC)

Core tables:

user_account

role

permission

role_permission

user_role

Every access decision must pass through RBAC.

---

# 10. Role Categories

System Administrator

Kendra Administrator

Parichalak

President

Secretary

Treasurer

Office Bearer

Regular Member

Probationary Member

Read-Only User

---

# 11. Permission Model

Permissions shall be action-based.

Examples:

person.view

person.create

person.edit

person.delete

membership.approve

attendance.review

governance.assign

report.export

---

# 12. Row Level Security (RLS)

Data visibility shall be restricted by organizational scope.

Examples:

Kendra
→ All Records

Anchalika
→ Assigned Anchalika

Zilla
→ Assigned Zilla

Sakha
→ Assigned Sakha

Member
→ Own Data

---

# 13. Organizational Scope

Scope Types:

KENDRA

ANCHALIKA

ZILLA

SAKHA

PERSONAL

Access outside assigned scope is prohibited.

---

# 14. Sensitive Data

Sensitive data includes:

Government IDs

Personal Contact Information

Birth Dates

Financial Data

Authentication Data

Sensitive data must be protected.

---

# 15. Encryption Standards

Encryption at Rest

Encryption in Transit

HTTPS Mandatory

TLS 1.2+

Sensitive fields may be encrypted.

---

# 16. Login Audit

Every login attempt shall be logged.

Fields:

Timestamp

Username

IP Address

Device Information

Result

Success / Failure

---

# 17. Security Event Logging

Track:

Login Failures

Password Changes

Role Assignments

Permission Changes

Account Locking

Account Unlocking

Data Export

Data Import

---

# 18. Administrator Controls

Administrators may:

Unlock Accounts

Reset Passwords

Assign Roles

Deactivate Accounts

Review Audit Logs

Administrators may not alter audit history.

---

# 19. API Security

All APIs require authentication.

Authorization checks mandatory.

Rate limiting supported.

Audit logging mandatory.

---

# 20. Data Export Security

Exports shall be logged.

Export authority must be permission controlled.

Large exports may require approval.

---

# 21. Security Reviews

Periodic review required for:

Roles

Permissions

Inactive Accounts

Failed Login Patterns

Audit Exceptions

---

# 22. Incident Response

Security incidents shall record:

Detection Date

Reported By

Impact

Actions Taken

Resolution Date

Root Cause

---

# 23. Security Principles Summary

Least Privilege

RBAC First

RLS Enforcement

Audit Everything

Encrypt Sensitive Data

Never Trust Client Input

Security Before Convenience
