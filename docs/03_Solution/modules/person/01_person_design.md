# NSS ERP Person Module Design

Version: 1.0

Status: DRAFT

---

# Purpose

The Person Module is the foundation of NSS ERP.

Every individual known to NSS shall exist as a Person.

A Person may or may not be a Member.

---

# Core Principle

Person ≠ Member

A person can exist without membership.

Membership is an additional relationship.

---

# Examples

Person Only

* Family member
* Spouse
* Child
* Kumari participant
* Kishore participant
* Historical person
* Future applicant

Person + Member

* Probationary Member
* Regular Member
* Associate Member

---

# Identity Model

Every person receives:

person_code

Example:

P00000001

P00000002

P00000003

Generated automatically.

---

# Person Lifecycle

Person Created
↓
Family Linked
↓
Membership Application (Optional)
↓
Membership Approved
↓
Sangha Sevi ID Generated

---

# Relationship with Membership

Person
1
│
│
0..1
Membership

A person may never become a member.

A member must always be a person.

---

# Relationship with Family

Person
│
▼
Family Group

Every person may belong to a family group.

Family membership is independent of NSS membership.

---

# Relationship with Kumari Sangha

Person
│
▼
Kumari Participation

A Kumari participant remains a person even after Kumari membership ends.

---

# Relationship with Kishore Puja

Person
│
▼
Kishore Participation

A Kishore participant remains a person permanently.

---

# Core Person Information

Person Code

First Name

Middle Name

Last Name

Gender

Date of Birth

Mobile Number

Email

Marital Status

Photo

---

# Information Deferred

The following items will be handled by future modules:

Aadhaar

Voter ID

Passport

Educational History

Employment History

Document Management

---

# Audit Requirements

Created By

Updated By

Deleted By

Timestamp

Reason

---

# Design Principles

Person First

Membership Separate

Family First

History Preserved

Audit Enabled

Soft Delete Enabled

Privacy Aware
