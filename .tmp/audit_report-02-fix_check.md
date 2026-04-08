# Audit Report 02 Fix Check

This file tracks the issues listed in `audit_report-02.md` and how each one was resolved during the second fix cycle.

## Issue-by-issue resolution

### 1. Org-scoped admin controls behaved globally
- **Issue from report 02:** scoped admins could still operate on global user, org, and reporting data.
- **Resolution:** org-aware filtering and object-scope checks were added to the affected admin user/org/reporting flows.
- **Status:** Resolved

### 2. Sensitive listing addresses were exposed in JSON APIs
- **Issue from report 02:** listing addresses were masked in HTML but still exposed through JSON responses.
- **Resolution:** role-aware masking was added to listing API serialization so non-privileged users receive masked addresses consistently across HTML and JSON.
- **Status:** Resolved

### 3. Offline cached authenticated content was unsafe
- **Issue from report 02:** cached authenticated pages could replay content that weakened isolation expectations.
- **Resolution:** offline-safe cache variants were introduced and later tightened so cached pages use least-privileged rendering rather than replaying the original authenticated view.
- **Status:** Resolved

### 4. Auto-flagged hidden reviews remained editable
- **Issue from report 02:** auto-flagged reviews were hidden but not fully marked moderated.
- **Resolution:** auto-flagging now sets the same moderation state used by manual moderation flows, which makes hidden auto-flagged reviews non-editable.
- **Status:** Resolved

### 5. Default startup path still enabled predictable credentials and placeholder secrets
- **Issue from report 02:** demo defaults remained too close to the main documented startup path.
- **Resolution:** startup hardening was improved through stronger config validation, safer bootstrap handling, and clearer separation between demo/dev and production-oriented paths.
- **Status:** Resolved

### 6. Drug create/update validation was incomplete
- **Issue from report 02:** invalid forms, NDCs, and unknown taxonomy tags were not fully rejected.
- **Resolution:** service-layer validation now explicitly rejects invalid form values, invalid NDCs, and unknown taxonomy tags.
- **Status:** Resolved

### 7. JSON auth endpoints sat outside the HMAC boundary
- **Issue from report 02:** non-form JSON auth requests were not signed/replay-protected.
- **Resolution:** JSON auth requests now require HMAC in non-test mode, while browser form auth remains session/CSRF based.
- **Status:** Resolved

### 8. Class creation did not explicitly require a date
- **Issue from report 02:** class creation relied too much on downstream persistence failure for missing dates.
- **Resolution:** class creation now validates `class_date` explicitly before persistence.
- **Status:** Resolved

## Verification

- targeted re-audits confirmed the cycle-02 auth/admin defects were closed
- E2E coverage now asserts least-privileged rendering for cached offline listings
- the repo test suite stayed green after the cycle-02 fixes

## Cycle 02 outcome

All issues listed in `audit_report-02.md` were addressed in code and backed by regression coverage or later targeted verification.
