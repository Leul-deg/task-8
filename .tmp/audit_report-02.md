# Clinical Operations Portal Static Audit (Cycle 02)

## 1. Verdict
- Overall conclusion: **Partial Pass**

## 2. Scope and Static Verification Boundary
- What was reviewed:
  - documentation and delivery shape
  - app factory, config, middleware, and route registration
  - core domain models/services
  - frontend templates and offline logic
  - unit/API/E2E test entry points
- What was not reviewed:
  - exhaustive CSS/template detail
  - external platform/runtime behavior
- What was intentionally not executed:
  - application startup
  - tests
  - Docker
  - background workers
  - backup/restore flows
- Which claims require manual verification:
  - real runtime startup and browser behavior
  - queue/worker execution in live conditions
  - restore timing and DR performance

## 3. Repository / Requirement Mapping Summary
- Core business goal:
  - same clinical operations portal baseline as cycle 01, with special emphasis in this cycle on admin/reporting scope, masking, auth boundary behavior, moderation-state consistency, and offline safety
- Main implementation areas mapped:
  - admin APIs/pages: `app/api/admin_routes.py`, `app/api/page_routes.py`
  - auth and registration boundary: `app/api/auth_routes.py`
  - listing JSON/API masking and offline behavior: `app/api/listing_routes.py`, `app/static/js/sw.js`
  - moderation and review editing: `app/services/moderation_service.py`, `app/services/review_service.py`
  - drug validation and JSON auth signing: `app/services/drug_service.py`, `app/api/auth_routes.py`

## 4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Documentation and static verifiability
- Conclusion: Pass
- Rationale: Startup/config/test artifacts remained statically understandable and coherent.
- Evidence: `README.md:12`, `README.md:76`, `docker-compose.yml:1`, `.env.example:1`

#### 1.2 Material deviation from the Prompt
- Conclusion: Partial Pass
- Rationale: The app still targeted the correct business domain, but the second-cycle baseline identified material security/compliance mismatches around admin scope, JSON masking, offline cached content, JSON auth signing, and validation depth.
- Evidence: `app/api/admin_routes.py:21`, `app/api/listing_routes.py:19`, `app/static/js/sw.js:190`

### 2. Delivery Completeness

#### 2.1 Core requirement coverage
- Conclusion: Partial Pass
- Rationale: Core business modules remained present, but key prompt-alignment details still needed hardening in this baseline snapshot.
- Evidence: `app/api/admin_routes.py:198`, `app/api/auth_routes.py:64`, `app/services/drug_service.py:11`

#### 2.2 End-to-end 0→1 deliverable
- Conclusion: Pass
- Rationale: The repository remained a complete full-stack product rather than a demo fragment.
- Evidence: `app/__init__.py:13`, `app/api/__init__.py:15`, `API_tests/test_admin_api.py:4`

### 3. Engineering and Architecture Quality

#### 3.1 Structure and module decomposition
- Conclusion: Pass
- Rationale: The route/service/model split remained clear and maintainable.
- Evidence: `app/services/audit_service.py:1`, `app/api/admin_routes.py:1`, `app/services/drug_service.py:1`

#### 3.2 Maintainability and extensibility
- Conclusion: Partial Pass
- Rationale: The structure was sound, but policy consistency across admin/report/offline/auth boundaries still needed consolidation.
- Evidence: `app/api/admin_routes.py:21`, `app/static/js/sw.js:190`, `app/api/auth_routes.py:28`

### 4. Engineering Details and Professionalism

#### 4.1 Professional engineering details
- Conclusion: Partial Pass
- Rationale: Validation and status handling were improving, but this cycle still identified material defects in admin scope, API masking, offline safety, auth HMAC scope, and class-date validation.
- Evidence: `app/api/listing_routes.py:19`, `app/services/moderation_service.py:31`, `app/services/drug_service.py:10`

#### 4.2 Product-like organization
- Conclusion: Pass
- Rationale: The app remained product-like while the remaining work was focused on hardening rather than missing whole modules.
- Evidence: `app/templates/base.html:20`, `app/templates/admin/backups.html:1`, `README.md:63`

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Business goal and constraint fit
- Conclusion: Partial Pass
- Rationale: This cycle reflected strong prompt understanding, but the baseline still had gaps around least-privileged offline behavior and cross-scope governance.
- Evidence: `app/api/auth_routes.py:64`, `app/api/admin_routes.py:198`, `app/static/js/sw.js:190`

### 6. Aesthetics

#### 6.1 Visual and interaction quality
- Conclusion: Pass
- Rationale: The interface remained coherent and scenario-appropriate.
- Evidence: `app/templates/base.html:15`, `app/templates/listings/detail.html:10`, `app/templates/classes/detail.html:38`

## 5. Issues / Suggestions (Severity-Rated)

### High
- **Severity:** High
  **Title:** Org-scoped admin controls behaved globally
  **Conclusion:** Fail
  **Evidence:** `app/api/admin_routes.py:21`, `app/api/page_routes.py:30`
  **Impact:** Scoped admins could still operate on global user/org/report data.
  **Minimum actionable fix:** Thread org scope through admin queries and object checks.

- **Severity:** High
  **Title:** Sensitive listing addresses were exposed in JSON APIs
  **Conclusion:** Fail
  **Evidence:** `app/models/listing.py:84`, `app/api/listing_routes.py:64`
  **Impact:** HTML masking could be bypassed through JSON responses.
  **Minimum actionable fix:** Apply role-aware masking in API serialization too.

- **Severity:** High
  **Title:** Offline cached authenticated content was unsafe
  **Conclusion:** Fail
  **Evidence:** `app/static/js/sw.js:208`, `e2e_tests/test_e2e.py:262`
  **Impact:** Cached authenticated HTML could weaken isolation expectations.
  **Minimum actionable fix:** Use offline-safe variants and least-privileged cached rendering.

- **Severity:** High
  **Title:** Auto-flagged hidden reviews remained editable
  **Conclusion:** Fail
  **Evidence:** `app/services/moderation_service.py:31`, `app/services/review_service.py:47`
  **Impact:** Hidden reviews were not consistently marked moderated.
  **Minimum actionable fix:** Set moderation state during auto-flag so edit protection applies.

- **Severity:** High
  **Title:** Default startup path still enabled predictable credentials and placeholder secrets
  **Conclusion:** Fail
  **Evidence:** `README.md:14`, `docker-compose.yml:10`, `scripts/seed_data.py:106`
  **Impact:** Demo defaults remained too close to the primary documented delivery path.
  **Minimum actionable fix:** isolate bootstrap/demo behavior and strengthen config validation.

### Medium
- **Severity:** Medium
  **Title:** Drug create/update validation was incomplete
  **Conclusion:** Partial Fail
  **Evidence:** `app/services/drug_service.py:10`, `app/utils/validators.py:72`
  **Impact:** Invalid form/NDC/tag input could slip through.
  **Minimum actionable fix:** validate those fields explicitly and reject unknown taxonomy tags.

- **Severity:** Medium
  **Title:** JSON auth endpoints sat outside the HMAC boundary
  **Conclusion:** Partial Fail
  **Evidence:** `app/api/auth_routes.py:28`, `app/api/middleware.py:23`
  **Impact:** non-form JSON auth traffic was not signed/replay-protected.
  **Minimum actionable fix:** require HMAC for non-form JSON auth requests or narrow/document the contract.

- **Severity:** Medium
  **Title:** Class creation did not explicitly require a date
  **Conclusion:** Partial Fail
  **Evidence:** `app/services/review_service.py:111`, `app/models/training.py:14`
  **Impact:** missing-date behavior relied too much on downstream persistence.
  **Minimum actionable fix:** validate `class_date` explicitly before persistence.

## 6. Security Review Summary
- authentication entry points: Partial Pass
  - Evidence: `app/api/auth_routes.py:28`, `app/services/auth_service.py:51`
  - Reasoning: auth was broadly solid, but JSON auth signing and self-registration org assignment were still open in this baseline.
- route-level authorization: Partial Pass
  - Evidence: `app/utils/decorators.py:6`, `app/api/admin_routes.py:21`
  - Reasoning: core guarding existed, but scoped admin/report paths were still too broad.
- object-level authorization: Partial Pass
  - Evidence: `app/api/listing_routes.py:64`, `app/api/admin_routes.py:61`
  - Reasoning: object checks were improving, but important admin/listing/offline paths still needed work.
- function-level authorization: Partial Pass
  - Evidence: `app/services/review_service.py:47`, `app/services/drug_service.py:10`
  - Reasoning: service-layer rules existed, but auto-flag moderation and drug validation still needed hardening.
- tenant / user data isolation: Fail
  - Evidence: `app/api/auth_routes.py:64`, `app/api/admin_routes.py:198`, `app/static/js/sw.js:208`
  - Reasoning: registration assignment, admin scope, and cached authenticated content still created isolation concerns.
- admin / internal / debug protection: Partial Pass
  - Evidence: `app/api/admin_routes.py:21`, `app/api/page_routes.py:42`
  - Reasoning: admin surfaces were guarded, but not yet scoped correctly.

## 7. Tests and Logging Review
- Unit tests: Pass
  - Evidence: `unit_tests/test_audit_service.py:61`, `unit_tests/test_moderation_service.py:79`
- API / integration tests: Pass (existence), Partial Pass (coverage depth)
  - Evidence: `API_tests/test_admin_api.py:4`, `API_tests/test_hmac_integration.py:232`
- Logging categories / observability: Partial Pass
  - Evidence: `app/services/audit_service.py:46`, `app/__init__.py:155`
- Sensitive-data leakage risk in logs / responses: Partial Pass
  - Evidence: `app/models/listing.py:84`, `app/services/audit_service.py:15`

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Unit tests existed under `unit_tests/`
- API / integration tests existed under `API_tests/`
- E2E tests existed under `e2e_tests/`
- test commands were documented in `README.md` and `run_tests.sh`
- Evidence: `run_tests.sh:61`, `README.md:76`, `API_tests/conftest.py:9`, `e2e_tests/test_e2e.py:1`

### 8.2 Coverage Mapping Table
| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
| --- | --- | --- | --- | --- | --- |
| registration must not self-assign org scope | later covered in fix-check | baseline had no matching coverage | missing in this baseline | self-registration org assignment | add auth API regression test |
| scoped admin audit/report/revoke boundaries | later covered in fix-check | baseline had no matching org-aware admin coverage | missing in this baseline | global admin/report scope | add admin API scope tests |
| listing JSON masking by role | later covered in fix-check | baseline had page masking but not JSON masking | insufficient in this baseline | JSON leakage of masked data | add API masking assertions |
| offline cached-content safety | later covered in fix-check | baseline E2E did not enforce least-privileged cached content | insufficient in this baseline | privileged cached HTML replay | add offline cached-content E2E assertions |
| drug validation for form/NDC/tag | some drug tests existed | duplicate/import checks only | insufficient in this baseline | create/update invalid payloads | add API/unit invalid-input tests |
| JSON auth HMAC boundary | HMAC tests existed for `/api/*` | auth JSON endpoints not covered | insufficient in this baseline | unsigned JSON auth traffic | add JSON auth HMAC tests |

### 8.3 Security Coverage Audit
- authentication: partial in this baseline
- route authorization: partial in this baseline
- object-level authorization: partial in this baseline
- tenant / data isolation: insufficient in this baseline
- admin / internal protection: partial in this baseline

Reasoning:
- the suite already covered many core mechanics
- but severe defects around admin scope, JSON masking, cached authenticated content, and JSON auth signing could still have shipped in the baseline

### 8.4 Final Coverage Judgment
- **Partial Pass**

Covered well:
- core auth flows
- many listing/review/moderation workflows
- HMAC basics

Still uncovered enough to matter in this baseline:
- scoped admin/report behavior
- JSON masking
- offline cached authenticated-content safety
- JSON auth signing
- stronger drug validation

## 9. Final Notes
- This report is the baseline second-cycle audit, not the final fixed state.
- The later remediation state is summarized in `audit_report-02-fix_check.md`.
