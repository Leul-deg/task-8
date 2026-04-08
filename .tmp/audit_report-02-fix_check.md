# Audit Report 02 Fix Check

This file summarizes the fixes made during the second remediation cycle.

## Cycle 02 fixes

### 1. Public registration org assignment

- **Issue:** self-registration still allowed a new user to choose an org unit directly.
- **Fix:** removed public org assignment from registration and rejected `org_unit_id` in the registration handler.
- **Result:** org membership creation is no longer user-supplied through public signup.

### 2. Admin audit and reporting scope

- **Issue:** scoped admins could still see global audit/report data.
- **Fix:** added org-aware filtering to audit-log and permission-audit flows.
- **Result:** reporting data now follows the same org boundaries as other protected admin operations.

### 3. Temp-grant revoke scoping

- **Issue:** revocation could target grants that belonged to out-of-scope users.
- **Fix:** added scope validation on the grant’s target user before revoke is allowed.
- **Result:** scoped admins cannot mutate temp grants outside their org boundary.

### 4. Listing JSON masking

- **Issue:** listing addresses were masked in HTML but exposed through JSON APIs.
- **Fix:** applied role-aware masking in listing API serialization as well.
- **Result:** non-privileged users now get masked listing addresses consistently across HTML and JSON.

### 5. Auto-flag moderation consistency

- **Issue:** auto-flagged reviews were hidden but not fully marked moderated.
- **Fix:** auto-flagging now sets the same moderation state used by manual moderation flows.
- **Result:** hidden auto-flagged reviews are non-editable and auditable in the same way as manually moderated reviews.

### 6. Drug validation

- **Issue:** create/update paths did not fully reject invalid forms, NDCs, or unknown taxonomy tags.
- **Fix:** added service-layer validation for those fields and rejected unknown taxonomy tags explicitly.
- **Result:** drug data integrity is stronger for both API and page-backed flows.

### 7. JSON auth signing

- **Issue:** JSON auth endpoints were outside the HMAC boundary.
- **Fix:** non-form JSON auth requests now require HMAC, while browser form auth remains session/CSRF based.
- **Result:** the signed-API contract is more consistent without breaking browser login/register flows.

### 8. Explicit class-date validation

- **Issue:** class creation relied too much on downstream persistence failure for missing dates.
- **Fix:** class creation now validates `class_date` explicitly as required input.
- **Result:** users receive proper validation behavior instead of indirect database failure paths.

### 9. Offline-safe cache variants

- **Issue:** authenticated cached pages initially removed username/logout in the shell but could still preserve privileged page-body content.
- **Fix:** introduced explicit offline-safe variants and then tightened them further for listings:
  - shell content is anonymized
  - address fields are forcibly masked
  - privileged controls like create/edit actions are hidden
- **Result:** offline-cached pages preserve read-most usability without replaying privileged-only listing visibility.

## Verification

- targeted re-audits confirmed the major auth/admin defects were closed
- E2E coverage now asserts least-privileged rendering for cached offline listings
- the repo test suite stayed green after the cycle-02 fixes

## Cycle 02 outcome

Cycle 02 closed the remaining issues around:

- registration boundary control
- scoped admin reporting
- temp-grant revoke scope
- JSON/API masking consistency
- moderation-state consistency
- stronger drug validation
- JSON auth HMAC coverage
- safer offline cached-content rendering
