# HR Contact List — Initial Cleaning Audit

**Source:** User-provided pasted export dated 2026-10-15. This report describes that uploaded text file, not a live Google Sheet.
**Data handling:** Aggregate-only report. Contact names and email addresses are intentionally excluded from this public repository.

## Results

| Metric | Count |
|---|---:|
| Source rows parsed | 4,727 |
| Unique normalized email keys | 3,570 |
| Duplicate email groups | 994 |
| Excess duplicate rows beyond first occurrence | 1,157 |
| Unique email groups with invalid/suspicious email syntax | 178 |
| Source rows with missing person name | 1,583 |
| Unique email groups with no person name anywhere in group | 1,579 |
| Email groups listed under multiple company labels | 986 |
| Source rows in review queue | 3,865 |

## Cleaning approach

- Reconstructed tab-separated records where fields were wrapped over multiple lines.
- Normalized whitespace and compared email keys case-insensitively.
- Preserved conflicting company labels rather than silently guessing the correct employer.
- Kept a review queue for duplicate, syntax, missing/conflicting-name, and company-label concerns.

## Important limitations

- Syntax validation does not prove that a mailbox exists or is deliverable.
- No DNS, mailbox, current employment, contact provenance, consent, opt-out, or vacancy verification was performed.
- The first occurrence supplies the primary company label; conflicting labels require review.
- Do not use this list for bulk outreach until provenance, relevance, recipient expectations, applicable rules, and opt-out handling have been reviewed.
- The source Google Sheet was not edited, and no emails or job applications were sent.

## Local artifacts (not committed here)

- `hr_contacts_deduplicated.csv`: one row per normalized email key, with source rows and company-label history.
- `hr_contacts_review_queue.csv`: source rows flagged for human review.

These CSVs contain contact-level personal data and must be stored in a private, access-controlled location—not in this public repository.
