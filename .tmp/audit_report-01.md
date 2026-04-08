# Clinical Operations Portal Static Audit

## 1. Verdict
- Overall conclusion: **Partial Pass**

## 2. Scope and Static Verification Boundary
- What was reviewed:
  - project docs/config (`README.md`, `.env.example`, `docker-compose.yml`, `Dockerfile`, `run_tests.sh`)
  - Flask app factory/config/routes/services/models/utils
  - templates/static assets
  - unit/API/E2E test code
- What was not reviewed:
  - external infrastructure
  - deployment environment
  - browser runtime behavior
  - actual backup restore operations
  - queue worker runtime behavior
- What was intentionally not executed:
  - app startup
  - tests
  - Docker
  - migrations
  - external services
- Which claims require manual verification:
  - offline queue replay behavior
  - HTMX/browser interactions
  - service-worker lifecycle across browsers
  - restore timing and DR targets (RPO/RTO)
  - production security posture after environment hardening

## 3. Repository / Requirement Mapping Summary
- Core business goal:
  - one offline-capable clinical operations portal covering listings, training reviews/moderation, and drug knowledge workflows
  - strong RBAC and org scoping
  - HMAC + replay protection
  - AES-GCM at-rest encryption
  - immutable audit logging
  - backup / DR support
- Main implementation areas mapped:
  - auth/session: `app/api/auth_routes.py`
  - RBAC/temp grants: `app/services/permission_service.py`
  - listings/reviews/moderation/drugs: route + service layers
  - HMAC middleware: `app/api/middleware.py`
  - encryption: `app/utils/crypto.py`
  - backups/queue: `app/services/backup_service.py`, `app/services/queue_service.py`
  - frontend/offline: `app/templates/*`, `app/static/js/sw.js`

## 4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Documentation and static verifiability
- Conclusion: Pass
- Rationale: Startup/config/test instructions and main entry points were statically discoverable and coherent.
- Evidence: `README.md:12`, `README.md:57`, `docker-compose.yml:1`, `run_tests.sh:1`

#### 1.2 Material deviation from the Prompt
- Conclusion: Partial Pass
- Rationale: The repo clearly targeted the requested business domains, but several core constraints were under-delivered in the baseline snapshot.
- Evidence: `app/static/js/sw.js:189`, `app/services/queue_service.py:84`, `app/templates/admin/index.html:9`
- Manual verification note: Runtime proof was outside scope.

### 2. Delivery Completeness

#### 2.1 Core requirement coverage
- Conclusion: Partial Pass
- Rationale: Core modules existed, but key controls like scope enforcement, backup UI completeness, queue operability, and offline behavior were incomplete in this baseline.
- Evidence: `app/api/listing_routes.py:37`, `app/services/backup_service.py:11`, `app/services/queue_service.py:84`

#### 2.2 End-to-end 0→1 deliverable
- Conclusion: Pass
- Rationale: The repository was a real multi-module application rather than a fragment or demo snippet.
- Evidence: `app/__init__.py:11`, `app/api/__init__.py:15`, `API_tests/test_page_flows.py:1`

### 3. Engineering and Architecture Quality

#### 3.1 Structure and module decomposition
- Conclusion: Pass
- Rationale: Models, services, routes, templates, and tests were separated reasonably.
- Evidence: `app/__init__.py:11`, `app/services/listing_service.py:85`, `app/models/listing.py:7`

#### 3.2 Maintainability and extensibility
- Conclusion: Partial Pass
- Rationale: The shape was maintainable, but cross-cutting security controls were inconsistent across endpoints.
- Evidence: `app/api/listing_routes.py:55`, `app/api/review_routes.py:71`, `app/api/moderation_routes.py:44`

### 4. Engineering Details and Professionalism

#### 4.1 Professional engineering details
- Conclusion: Partial Pass
- Rationale: Validation and audit logging existed, but multiple security-critical edge cases were still incorrectly handled in the baseline.
- Evidence: `app/services/auth_service.py:60`, `app/api/review_routes.py:71`, `app/services/backup_service.py:11`

#### 4.2 Product-like organization
- Conclusion: Partial Pass
- Rationale: The app looked product-like overall, but several compliance-critical workflows were still incomplete or mismatched.
- Evidence: `app/static/js/sw.js:189`, `app/templates/admin/index.html:9`, `app/services/queue_service.py:84`

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Business goal and constraint fit
- Conclusion: Partial Pass
- Rationale: The business domains and workflows were understood, but important constraints around security, scoping, offline behavior, and DR still needed work.
- Evidence: `app/api/listing_routes.py:37`, `app/api/moderation_routes.py:19`, `app/static/js/sw.js:191`

### 6. Aesthetics

#### 6.1 Visual and interaction quality
- Conclusion: Pass
- Rationale: Static UI structure showed coherent layout, HTMX interactions, and user feedback patterns.
- Evidence: `app/templates/base.html:15`, `app/templates/listings/detail.html:11`, `app/templates/moderation/partials/report_card.html:16`
- Manual verification note: Actual rendering/accessibility required browser execution.

## 5. Issues / Suggestions (Severity-Rated)

### Blocker / High
- **Severity:** High
  **Title:** Insecure production defaults and predictable bootstrap credentials
  **Conclusion:** Fail
  **Evidence:** `docker-compose.yml:9`, `scripts/seed_data.py:105`, `README.md:19`
  **Impact:** The default startup path allowed placeholder secrets and predictable bootstrap users.
  **Minimum actionable fix:** Require explicit production secrets and isolate demo/bootstrap behavior from the main delivery path.

- **Severity:** High
  **Title:** Missing org-scope authorization on critical listing and moderation paths
  **Conclusion:** Fail
  **Evidence:** `app/api/listing_routes.py:37`, `app/api/listing_page_routes.py:156`, `app/api/moderation_routes.py:19`
  **Impact:** Users could reach cross-org object and mutation paths without consistent scope enforcement.
  **Minimum actionable fix:** Enforce `user_accessible_org_ids` and object-level scope checks across create/read/mutate routes.

- **Severity:** High
  **Title:** Offline-first read-most requirement not implemented
  **Conclusion:** Fail
  **Evidence:** `app/static/js/sw.js:189`, `app/static/js/sw.js:191`
  **Impact:** The service worker left authenticated pages network-only, so the offline-read requirement was not met.
  **Minimum actionable fix:** Add a safe caching strategy for selected read-most screens with cache invalidation and isolation controls.

- **Severity:** High
  **Title:** Queue and retry architecture was non-operational
  **Conclusion:** Fail
  **Evidence:** `app/services/queue_service.py:84`, `app/__init__.py:44`
  **Impact:** Queue processing logic existed but had no practical execution path.
  **Minimum actionable fix:** Add an operational worker/cron/loop entrypoint that actually invokes pending job processing.

- **Severity:** High
  **Title:** Duplicate email validation was broken
  **Conclusion:** Fail
  **Evidence:** `app/services/auth_service.py:60`, `app/models/user.py:68`
  **Impact:** Duplicate emails could bypass uniqueness due to randomized encrypted storage.
  **Minimum actionable fix:** Add a deterministic normalized email hash for uniqueness checks.

- **Severity:** High
  **Title:** Admin backups console route was missing
  **Conclusion:** Fail
  **Evidence:** `app/templates/admin/index.html:9`, `app/api/page_routes.py:21`
  **Impact:** The UI advertised backup management but did not actually expose the page flow.
  **Minimum actionable fix:** Add `/admin/backups` page route and template backed by the existing backup services.

### Medium
- **Severity:** Medium
  **Title:** Status-code and error mapping inconsistencies
  **Conclusion:** Partial Fail
  **Evidence:** `app/api/review_routes.py:71`, `app/api/moderation_routes.py:44`
  **Impact:** Some permission and validation failures were mapped to the wrong status or could escalate poorly.
  **Minimum actionable fix:** Normalize exception handling by error type.

- **Severity:** Medium
  **Title:** Appeal resolution deadline not enforced
  **Conclusion:** Partial Fail
  **Evidence:** `app/services/moderation_service.py:138`, `app/services/moderation_service.py:159`
  **Impact:** SLA metadata existed without enforcement.
  **Minimum actionable fix:** Enforce the resolution deadline in the appeal resolution flow.

- **Severity:** Medium
  **Title:** Sensitive data exposure in audit payloads
  **Conclusion:** Partial Fail
  **Evidence:** `app/services/listing_service.py:115`, `app/services/auth_service.py:82`
  **Impact:** Audit records could contain raw sensitive values.
  **Minimum actionable fix:** Redact or sanitize sensitive fields before logging them.

## 6. Security Review Summary
- authentication entry points: Partial Pass
  - Evidence: `app/api/auth_routes.py:83`, `app/services/auth_service.py:87`
  - Reasoning: auth and login protections existed, but the baseline startup path weakened the posture.
- route-level authorization: Partial Pass
  - Evidence: `app/utils/decorators.py:6`, `app/api/listing_routes.py:40`, `app/api/admin_routes.py:24`
  - Reasoning: many routes were guarded, but some sensitive routes lacked full org/object scope.
- object-level authorization: Fail
  - Evidence: `app/api/listing_page_routes.py:156`, `app/api/moderation_routes.py:53`
  - Reasoning: direct object routes did not consistently enforce scope in the baseline.
- function-level authorization: Partial Pass
  - Evidence: `app/services/review_service.py:69`, `app/services/listing_service.py:155`
  - Reasoning: some business-layer guards existed, but not uniformly.
- tenant / user data isolation: Fail
  - Evidence: `app/api/listing_routes.py:27`, `app/api/moderation_routes.py:19`
  - Reasoning: cross-org isolation was incomplete on multiple critical paths.
- admin / internal / debug protection: Partial Pass
  - Evidence: `app/api/admin_routes.py:24`, `app/templates/admin/index.html:9`
  - Reasoning: admin routes were protected, but admin workflow completeness and scope were still lacking.

## 7. Tests and Logging Review
- Unit tests: Pass (existence), Partial Pass (depth)
  - Evidence: `unit_tests/test_hmac_middleware.py:1`, `unit_tests/test_listing_service.py:1`
- API / integration tests: Pass (existence), Partial Pass (critical gaps)
  - Evidence: `API_tests/test_authorization.py:1`, `API_tests/test_hmac_integration.py:1`
- Logging categories / observability: Partial Pass
  - Evidence: `app/services/audit_service.py:46`, `app/__init__.py:136`
- Sensitive-data leakage risk in logs / responses: Partial Fail
  - Evidence: `app/services/listing_service.py:115`, `app/services/auth_service.py:82`

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Unit tests exist under `unit_tests/`
- API / integration tests exist under `API_tests/`
- E2E tests exist under `e2e_tests/`
- Test entry points were documented in `README.md` and `run_tests.sh`
- Evidence: `unit_tests/test_auth_service.py:12`, `API_tests/conftest.py:9`, `e2e_tests/test_e2e.py:1`, `run_tests.sh:61`

### 8.2 Coverage Mapping Table
| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
| --- | --- | --- | --- | --- | --- |
| Auth login/logout/session boundary | `API_tests/test_auth_api.py:31`, `API_tests/test_page_flows.py:138` | logout/session-clear assertions | basically covered | no production-hardening test | add config-hardening tests |
| HMAC signing and replay protection | `unit_tests/test_hmac_middleware.py:75`, `API_tests/test_hmac_integration.py:104` | duplicate nonce and invalid signature checks | sufficient | endpoint matrix not exhaustive | add broader route matrix if needed |
| Listing workflow and status transitions | `unit_tests/test_listing_service.py:178`, `API_tests/test_listing_api.py:61` | invalid transition and status checks | basically covered | cross-org create not covered in baseline | add cross-org create denial |
| Object-level org isolation (listings) | `API_tests/test_authorization.py:140` | cross-org GET/PUT/POST status denials | basically covered | preview route gap in baseline | add preview denial test |
| Review authoring constraints | `unit_tests/test_review_service.py:53`, `API_tests/test_review_api.py:31` | attendee and duplicate constraints | sufficient | moderation/edit edge cases missing in baseline | add moderated review update tests |
| Backup and restore APIs | `unit_tests/test_backup_service.py:59`, `API_tests/test_admin_api.py:128` | encryption and restore input guards | basically covered | no UI route coverage in baseline | add `/admin/backups` page tests |

### 8.3 Security Coverage Audit
- authentication: basically covered
- route authorization: partial
- object-level authorization: partial
- tenant / data isolation: partial
- admin / internal protection: partial

Reasoning:
- several core security helpers were tested
- but severe scope defects could still remain undetected in the baseline because route coverage did not fully match the most sensitive object/mutation paths

### 8.4 Final Coverage Judgment
- **Partial Pass**

Covered well:
- auth and HMAC basics
- many listing/review workflow paths
- backup encryption and restore guards

Uncovered enough to matter in the baseline:
- cross-org scope gaps
- admin UI/route completeness
- offline-read behavior
- duplicate email integrity

## 9. Final Notes
- This report is the baseline first-cycle static audit, not the final fixed state.
- Subsequent remediation and verification are summarized in `audit_report-01-fix_check.md`.
