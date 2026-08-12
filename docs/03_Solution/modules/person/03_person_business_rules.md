# NSS ERP Person Business Rules

Version: 1.1

Status: DRAFT

---

# 1. Purpose

Defines the business rules governing Person records in NSS ERP.

These rules take precedence over database implementation.

---

# 2. Core Principle

Person ≠ Member

A Person may exist without membership.

A Member must always be a Person.

---

# 3. Person Code Rule

Every Person shall have a unique Person Code.

Examples:

P00000001

P00000002

P00000003

Generated automatically.

Person Code is permanent.

Person Code shall never be reused.

---

# 4. Person Creation Rule

A Person may be created through:

* Family Registration
* Membership Application
* Kumari Registration
* Kishore Registration
* Administrative Entry
* Historical Data Migration

---

# 5. Name Rule

First Name is mandatory.

Middle Name is optional.

Last Name is optional.

Name changes must preserve audit history.

---

# 6. Gender Rule

Gender must be selected from master data.

Allowed values managed through:

gender_master

---

# 7. Date of Birth Rule

Date of Birth is optional for Person records.

Date of Birth becomes mandatory before a Person can be approved as a Member.

Membership workflows shall validate the presence of Date of Birth before membership activation.

Partial information may be supported in future versions.

---

# 8. Mobile Number Rule

One primary mobile number may be maintained for a Person.

Mobile number is optional.

Mobile numbers shall support international formats.

A mobile number consists of:

* Country Phone Code
* Mobile Number

Examples:

Valid

+91 9876543210

+1 5551234567

+44 7700123456

A mobile number must be unique across all Person records when combined with Country Phone Code.

Valid

+91 9876543210

+1 9876543210

Invalid

+91 9876543210

+91 9876543210

If a duplicate mobile number is detected, the system shall prevent creation of the duplicate record and display the existing Person information for review.

Shared family mobile numbers shall not be duplicated across Person records.

Family communication requirements shall be handled through Family relationships and future Family Contact functionality.

Country Phone Code and Mobile Number must be provided together.

Valid

+91 + 9876543210

NULL + NULL

Invalid

+91 + NULL

NULL + 9876543210


---

# 9. Email Rule

One primary email address may be maintained for a Person.

Email is optional.

Email is not required to be unique.

Examples:

Valid

P00000001
→ [abc@example.com](mailto:abc@example.com)

P00000002
→ [abc@example.com](mailto:abc@example.com)

Shared family email addresses are permitted.

---

# 10. Contact Information Rule

Every Person must have at least one contact method.

At least one of the following must be provided:

* Mobile Number
* Email Address

Valid Examples

Mobile + NULL

NULL + Email

Mobile + Email

Invalid Example

NULL + NULL

The system shall prevent creation of a Person record when both Mobile Number and Email Address are NULL.

The database shall enforce this rule through a CHECK constraint.

Example:

CHECK (
mobile_number IS NOT NULL
OR
email IS NOT NULL
)

---

# 11. Marital Status Rule

Marital status shall be maintained through master data.

Examples:

* UNMARRIED
* MARRIED
* WIDOWED
* DIVORCED
* SEPARATED

---

# 12. Address Rule

A Person may have multiple addresses.

Examples:

* PERMANENT
* CURRENT
* OFFICIAL

Address types shall be managed through master data.

A Person may designate one address as the Primary Address.

At any point in time, only one address may be designated as the Primary Address.

The Primary Address may be changed by an authorized user.

When a new address is marked as Primary, the system shall automatically remove the Primary designation from the previous address.

A Person may have zero addresses during initial Person creation.

Address information may be added later.

The system shall enforce a maximum of one Primary Address per Person.

The system shall not require an address before Person creation.


---

# 13. Duplicate Detection Rule

Before creating a new Person, the system should check:

* Name
* Date of Birth
* Mobile Number
* Email

Potential matches should be flagged for review.

---

# 14. Merge Rule

Duplicate Person records may be merged.

Merge operations must:

* Preserve audit history
* Preserve references
* Maintain historical traceability

---

# 15. Membership Rule

While filling a Membership Application, a Personal Details page shall be completed mandatorily.

The applicant must provide all required Person information before Membership submission.

A Membership Application cannot be submitted until mandatory Person details are completed.

Date of Birth becomes mandatory during Membership Application submission.

---

# 16. Family Rule

Person records do not contain family relationships.

Family relationships belong to the Family Module.

---

# 17. Deletion Rule

Person records shall not be physically deleted.

Soft delete only.

Historical references must remain valid.

---

# 18. Audit Rule

All changes must capture:

* Created By
* Updated By
* Deleted By
* Timestamp
* Reason

---

# 19. Privacy Rule

Sensitive identity documents shall not be stored in Person v1.

Examples:

* Aadhaar
* Passport
* Voter ID

These will be handled by future Document Management modules.

---

# 20. Design Principles

* Person First
* Membership Separate
* Family First
* History Preserved
* Audit Enabled
* Soft Delete Enabled
* Privacy Aware
