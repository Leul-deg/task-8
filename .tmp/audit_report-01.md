# Clinical Operations Portal Static Audit

## 1. Verdict

- Overall conclusion: **Partial Pass**

## 2. Scope and Static Verification Boundary

- Reviewed:
  - project docs/config (`README.md`, `.env.example`, `docker-compose.yml`, `Dockerfile`, `run_tests.sh`)
  - Flask app factory/config/routes/services/models/utils
  - templates/static assets
  - unit/API/E2E test code
- Not reviewed:
  - external infrastructure
  - deployment environment
  - browser runtime behavior
  - actual backup restore operations
  - queue worker runtime behavior
- Intentionally not executed:
  - app startup, tests, Docker, migrations, external services
- Manual verification required for:
  - offline queue replay behavior
  - HTMX/browser interactions
  - service-worker lifecycle across browsers
  - restore timing and DR targets (RPO/RTO)
  - production security posture after environment hardening

## 3. Repository / Requirement Mapping Summary

- Prompt core goal:
  - single offline-capable clinical operations portal for listings, training reviews/moderation, and drug/knowledge workflows
  - multi-level RBAC with scoped data access
  - HMAC + replay protection
  - AES-GCM at-rest protection
  - immutable audits
  - admin backup / DR operations
- Main implementation areas initially mapped:
  - auth/session: `app/api/auth_routes.py`
  - RBAC/temp grants: `app/services/permission_service.py`
  - listings/reviews/moderation/drugs: services + routes
  - HMAC middleware: `app/api/middleware.py`
  - encryption: `app/utils/crypto.py`
  - backup service: `app/services/backup_service.py`
  - queue: `app/services/queue_service.py`
  - HTMX/service worker: `app/templates/*`, `app/static/js/sw.js`

## 4. Key Findings From The Initial Audit

### Blocker / High

1. **Insecure production defaults + bootstrap credentials**
   - Placeholder secrets and predictable bootstrap credentials were allowed in the default startup path.

2. **Missing org-scope authorization on critical listing/moderation paths**
   - Scope checks were incomplete on listing create/preview and moderation object flows.

3. **Offline-first read-most requirement not met**
   - Service worker cached only static assets and explicitly left authenticated pages network-only.

4. **Async queue / retry architecture non-operational**
   - Queue processor existed, but no execution path actually invoked it in the app flow.

5. **Duplicate email validation broken**
   - Email uniqueness used encrypted-field lookup, which could not work with randomized AES-GCM ciphertext.

6. **Admin backups console route missing**
   - Admin UI linked to backups but no matching page route/template existed.

### Medium

7. **Incorrect status-code / error mapping in some endpoints**
   - Some permission and validation failures were collapsed into the wrong response codes.

8. **Appeal resolution deadline stored but not enforced**
   - SLA data existed, but overdue resolution logic was not actually enforced.

9. **Sensitive data exposure in audit payloads**
   - Audit records could contain raw emails/addresses without sanitization.

## 5. Why This Report Matters

This first-cycle report established the baseline defects that drove the subsequent remediation passes:

- production hardening
- object/org scoping
- backup UI + restore operability
- queue worker activation
- audit sanitization
- email uniqueness integrity
- offline architecture

## 6. Follow-up

The corresponding fix-check for this first audit cycle is in:

- `audit_report-01-fix_check.md`
