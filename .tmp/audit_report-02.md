# Clinical Operations Portal Static Audit (Cycle 02)

## 1. Verdict

- Overall conclusion: **Fail**

## 2. Scope and Static Verification Boundary

- Reviewed:
  - documentation and delivery shape
  - app factory, config, middleware, and route registration
  - core domain models/services
  - frontend templates and offline logic
  - unit/API/E2E test entry points
- Not reviewed exhaustively:
  - every CSS rule / every partial
  - external platform/runtime behavior
- Intentionally not executed:
  - application startup
  - tests
  - Docker
  - background workers
  - backup/restore flows

## 3. Major Findings In Cycle 02 Report 01

### High

1. **Org-scoped admin controls behaved globally**
   - admin users/roles/temp-grants/org settings were not consistently scoped by org access

2. **Sensitive listing addresses were exposed in JSON APIs**
   - addresses were masked in HTML but still returned in decrypted form from listing JSON endpoints

3. **Offline cached authenticated content was unsafe**
   - authenticated HTML pages could be replayed in ways that weakened isolation expectations

4. **Auto-flagged hidden reviews remained editable**
   - hidden reviews were not consistently marked moderated

5. **Documented default startup path still enabled predictable credentials and placeholder secrets**
   - demo defaults remained too close to the primary delivery path

### Medium

6. **Drug create/update validation was incomplete**
   - invalid forms, NDC values, and unknown taxonomy tags were not fully rejected

7. **JSON auth endpoints sat outside the HMAC boundary**
   - non-form JSON auth traffic was not signed/replay-protected

8. **Class creation did not explicitly require a date**
   - missing-date behavior still depended too much on downstream persistence failure

## 4. Why Cycle 02 Was Important

This second-cycle baseline shifted attention from the original large architecture gaps toward:

- tighter admin/reporting scope
- response-level data masking
- auth-boundary correctness
- moderation state consistency
- stronger input validation
- safer offline behavior

## 5. Follow-up

The corresponding fix-check summary for cycle 02 is in:

- `audit_report-02-fix_check.md`
