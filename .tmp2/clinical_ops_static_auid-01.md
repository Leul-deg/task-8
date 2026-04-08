1. Verdict

- Overall conclusion: Fail

2. Scope and Static Verification Boundary

- Reviewed:
  - Documentation and delivery shape: `repo/README.md:1`, `repo/.env.example:1`, `repo/docker-compose.yml:1`, `repo/docker-compose.prod.yml:1`, `repo/Dockerfile:1`, `repo/run_tests.sh:1`
  - App factory, config, route registration, middleware: `repo/app/__init__.py:13`, `repo/app/config.py:12`, `repo/app/api/__init__.py:15`, `repo/app/api/middleware.py:9`, `repo/app/utils/decorators.py:6`
  - Core domains and persistence: `repo/app/models/listing.py:7`, `repo/app/models/training.py:6`, `repo/app/models/moderation.py:7`, `repo/app/models/drug.py:13`, `repo/app/models/audit.py:7`
  - Business logic and security-sensitive services: `repo/app/services/listing_service.py:91`, `repo/app/services/review_service.py:9`, `repo/app/services/moderation_service.py:27`, `repo/app/services/drug_service.py:10`, `repo/app/services/permission_service.py:37`, `repo/app/services/backup_service.py:11`, `repo/app/services/audit_service.py:46`
  - Frontend templates and offline logic: `repo/app/templates/base.html:1`, `repo/app/templates/listings/detail.html:1`, `repo/app/templates/classes/detail.html:1`, `repo/app/static/js/app.js:1`, `repo/app/static/js/sw.js:1`
  - Test suite and test entry points: `repo/API_tests/conftest.py:9`, `repo/e2e_tests/conftest.py:21`, `repo/unit_tests/test_hmac_middleware.py:24`, `repo/API_tests/test_hmac_integration.py:35`
- Not reviewed exhaustively:
  - Every CSS rule and every template partial line-by-line
  - External platform/runtime behavior not provable without execution
- Intentionally not executed:
  - The application, tests, Docker, browser flows, background workers, backup/restore, and any external services
- Manual verification required for:
  - Actual startup success and environment-specific behavior
  - Real service-worker behavior across browsers/workstations
  - Queue worker execution and retry behavior in a live deployment
  - Restore timing, nightly scheduling, RPO/RTO claims, and older workstation UX/performance

3. Repository / Requirement Mapping Summary

- Prompt core goal:
  - Offline-capable portal for property listings, training-class reviews/moderation, and clinical knowledge/drug content, with multi-level org scoping, RBAC, temp grants, auditability, HMAC/replay protection, encryption at rest, and backup/restore support.
- Main implementation areas mapped:
  - Auth/session and route registration: `repo/app/api/auth_routes.py:11`, `repo/app/api/__init__.py:15`
  - Listings workflow and org scoping: `repo/app/api/listing_routes.py:18`, `repo/app/services/listing_service.py:152`
  - Classes/reviews/moderation: `repo/app/api/class_page_routes.py:16`, `repo/app/api/review_routes.py:21`, `repo/app/api/moderation_routes.py:28`
  - Drug/knowledge base: `repo/app/api/drug_routes.py:19`, `repo/app/services/drug_service.py:126`
  - RBAC, temp grants, admin operations: `repo/app/services/permission_service.py:37`, `repo/app/api/admin_routes.py:21`
  - Security/offline/backup: `repo/app/api/middleware.py:9`, `repo/app/utils/crypto.py:61`, `repo/app/static/js/sw.js:182`, `repo/app/services/backup_service.py:11`

4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Documentation and static verifiability

- Conclusion: Pass
- Rationale: The delivery includes a readable README, environment guidance, documented routes, project structure, compose files, and a test runner, so a human reviewer can statically understand entry points and expected setup. Runtime claims still require manual verification.
- Evidence: `repo/README.md:12`, `repo/README.md:77`, `repo/README.md:178`, `repo/docker-compose.yml:1`, `repo/docker-compose.prod.yml:1`, `repo/run_tests.sh:1`
- Manual verification note: Startup, queue worker, service worker, and restore behavior were not executed.

#### 1.2 Whether the delivered project materially deviates from the Prompt

- Conclusion: Partial Pass
- Rationale: The repository is centered on the requested business domains, but material deviations remain in security and scope enforcement. Org-scoped admin controls are not actually scoped, masked listing data is exposed via API, and offline page caching can outlive auth boundaries.
- Evidence: `repo/app/api/admin_routes.py:21`, `repo/app/services/permission_service.py:71`, `repo/app/api/listing_routes.py:61`, `repo/app/models/listing.py:84`, `repo/app/static/js/sw.js:208`
- Manual verification note: Any claim about actual exploitability in a browser session still requires manual verification, but the static design flaw is evident.

### 2. Delivery Completeness

#### 2.1 Core requirement coverage

- Conclusion: Partial Pass
- Rationale: Listings, classes/reviews, moderation, drugs, temp grants, audit logs, encryption, HMAC, and backups are implemented. Coverage is incomplete against prompt-critical constraints: admin data scope is not enforced, non-privileged masking is UI-only, some API surfaces are outside HMAC signing, and drug input validation is weaker than the prompt requires.
- Evidence: `repo/app/api/listing_routes.py:18`, `repo/app/api/review_routes.py:21`, `repo/app/api/moderation_routes.py:28`, `repo/app/api/drug_routes.py:19`, `repo/app/api/admin_routes.py:21`, `repo/app/api/auth_routes.py:28`, `repo/app/services/drug_service.py:10`
- Manual verification note: Booking-related behavior is not directly verifiable from the delivered interfaces and would need requirement clarification plus runtime inspection.

#### 2.2 Basic end-to-end deliverable vs partial/demo

- Conclusion: Pass
- Rationale: The repo has a coherent Flask app, data models, templates, services, tests, Dockerfiles, and docs. It is substantially more than a code fragment or teaching sample, even though some defaults are demo-like and insecure.
- Evidence: `repo/README.md:178`, `repo/app/__init__.py:13`, `repo/app/api/__init__.py:15`, `repo/app/templates/base.html:1`, `repo/unit_tests/test_models.py:36`, `repo/API_tests/test_page_flows.py:138`

### 3. Engineering and Architecture Quality

#### 3.1 Engineering structure and module decomposition

- Conclusion: Pass
- Rationale: The repository is separated into models, services, API/page routes, templates, static assets, and tests. Responsibilities are generally understandable and not piled into one file.
- Evidence: `repo/README.md:178`, `repo/app/api/__init__.py:1`, `repo/app/models/__init__.py:1`, `repo/app/services/listing_service.py:1`, `repo/app/services/review_service.py:1`

#### 3.2 Maintainability and extensibility

- Conclusion: Partial Pass
- Rationale: The overall decomposition is maintainable, but security-critical behavior is split across page routes, JSON/API routes, service worker logic, and permission helpers in ways that create inconsistent enforcement. The admin area is especially coupled to unscoped global queries.
- Evidence: `repo/app/api/admin_routes.py:21`, `repo/app/api/page_routes.py:30`, `repo/app/services/permission_service.py:37`, `repo/app/static/js/sw.js:208`

### 4. Engineering Details and Professionalism

#### 4.1 Error handling, logging, validation, API design

- Conclusion: Fail
- Rationale: The codebase has solid pieces of validation and audit logging, but several prompt-critical engineering details fail materially: org-scoped admin actions are not scoped, sensitive listing fields are returned unmasked from APIs, auto-flagged reviews remain editable, and drug creation/update lack robust validation despite validators existing.
- Evidence: `repo/app/services/audit_service.py:46`, `repo/app/services/listing_service.py:27`, `repo/app/api/admin_routes.py:21`, `repo/app/api/listing_routes.py:61`, `repo/app/services/moderation_service.py:31`, `repo/app/services/review_service.py:47`, `repo/app/services/drug_service.py:10`, `repo/app/utils/validators.py:72`
- Manual verification note: Logging categories appear limited in normal request flow; only static evidence of exception logging/audit logging was reviewed.

#### 4.2 Real product/service vs example/demo

- Conclusion: Partial Pass
- Rationale: The deliverable looks like a real internal web app, but the default quick-start path is still demo-oriented: predictable bootstrap accounts and placeholder secrets are enabled in the default compose file, which weakens professional delivery quality.
- Evidence: `repo/README.md:14`, `repo/README.md:19`, `repo/docker-compose.yml:10`, `repo/docker-compose.yml:13`, `repo/docker-compose.yml:16`, `repo/scripts/seed_data.py:106`

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Business-goal and constraint fit

- Conclusion: Partial Pass
- Rationale: The implementation clearly understands the requested domains and several nuanced constraints, including review anonymity modes, appeal windows, listing status workflow, backup encryption, and temp-grant expiry. The most important misses are around security/compliance boundaries that the prompt treats as first-class requirements.
- Evidence: `repo/app/api/admin_routes.py:143`, `repo/app/services/moderation_service.py:123`, `repo/app/services/listing_service.py:152`, `repo/app/services/backup_service.py:11`, `repo/app/services/permission_service.py:145`, `repo/app/static/js/sw.js:208`

### 6. Aesthetics

#### 6.1 Visual and interaction design fit

- Conclusion: Pass
- Rationale: Staticaly, the templates show a coherent English-language interface with distinct functional areas, badges, cards, filters, modal preview, offline/queue banners, and HTMX partial updates. Full rendering quality and older-workstation interaction performance remain manual-verification items.
- Evidence: `repo/app/templates/base.html:15`, `repo/app/templates/listings/index.html:5`, `repo/app/templates/listings/detail.html:10`, `repo/app/templates/classes/detail.html:38`, `repo/app/templates/moderation/queue.html:4`
- Manual verification note: Actual browser rendering, accessibility, and responsiveness were not executed.

5. Issues / Suggestions (Severity-Rated)

#### High

1. Severity: High
   Title: Org-scoped admin controls are implemented as global controls
   Conclusion: Fail
   Evidence: `repo/app/api/admin_routes.py:21`, `repo/app/api/admin_routes.py:46`, `repo/app/api/admin_routes.py:76`, `repo/app/api/admin_routes.py:134`, `repo/app/api/page_routes.py:30`, `repo/app/api/page_routes.py:63`, `repo/app/services/permission_service.py:71`
   Impact: A user with admin permissions scoped to one org unit can list users, assign roles, grant temp permissions, and change org settings globally because admin routes never pass an `org_unit_id` into permission checks. This breaks the prompt’s org-unit data-scope requirement and creates cross-campus privilege escalation/data exposure risk.
   Minimum actionable fix: Thread org scope through admin endpoints and queries; require explicit target org context; filter users/org units by `user_accessible_org_ids()` or equivalent; reject out-of-scope operations at route and service level; add cross-org admin authorization tests.

2. Severity: High
   Title: Sensitive listing addresses are masked in HTML but exposed in JSON APIs
   Conclusion: Fail
   Evidence: `repo/app/models/listing.py:84`, `repo/app/api/listing_routes.py:64`, `repo/app/api/listing_routes.py:130`, `repo/app/templates/listings/detail.html:27`, `repo/API_tests/test_page_flows.py:698`
   Impact: Same-org non-privileged users can call listing JSON endpoints and receive full decrypted address fields even though the UI masks them. The masking requirement is therefore bypassable by the browser/API surface.
   Minimum actionable fix: Apply role-aware masking in JSON serialization as well as templates, or provide separate masked/unmasked serializers with permission checks; add API tests proving staff users cannot retrieve full addresses.

3. Severity: High
   Title: Offline page cache can serve authenticated content without revalidating auth
   Conclusion: Fail
   Evidence: `repo/app/__init__.py:167`, `repo/app/static/js/sw.js:208`, `repo/app/static/js/sw.js:216`, `repo/app/static/js/app.js:12`, `repo/app/static/js/app.js:21`, `repo/e2e_tests/test_e2e.py:262`, `repo/e2e_tests/test_e2e.py:348`
   Impact: The service worker intentionally stores authenticated read-most pages and returns them offline from cache without checking session state. On a shared workstation or after cookie loss/expiry, stale authenticated pages may still be readable offline. This contradicts the `no-store` intent and weakens data-isolation guarantees.
   Minimum actionable fix: Do not cache authenticated HTML directly, or encrypt/cache only non-sensitive fragments keyed to the active session with strict purge semantics; add tests for offline access after logout, cookie expiry, and user switch to prove unauthorized offline reads are impossible.

4. Severity: High
   Title: Auto-flagged hidden reviews are not marked moderated and remain editable
   Conclusion: Fail
   Evidence: `repo/app/services/moderation_service.py:31`, `repo/app/services/review_service.py:47`
   Impact: Keyword-flagged reviews are hidden but `is_moderated` is never set, while review edits are blocked only when `is_moderated` is true. That allows a review already hidden by offline moderation rules to remain editable, weakening the moderation workflow and auditability.
   Minimum actionable fix: When auto-flagging, set the same moderation state used by manual hide flows (`is_moderated`, moderation reason, any related status flags) and add tests that hidden auto-flagged reviews cannot be edited or repeatedly auto-reported.

5. Severity: High
   Title: Default documented startup path enables predictable credentials and placeholder secrets
   Conclusion: Fail
   Evidence: `repo/README.md:14`, `repo/README.md:19`, `repo/README.md:21`, `repo/docker-compose.yml:10`, `repo/docker-compose.yml:13`, `repo/docker-compose.yml:14`, `repo/docker-compose.yml:15`, `repo/docker-compose.yml:16`, `repo/scripts/seed_data.py:106`, `repo/scripts/seed_data.py:116`, `repo/scripts/seed_data.py:131`
   Impact: The primary quick-start path creates a default `admin` account with a predictable password and placeholder crypto/HMAC secrets. Even if framed as local/demo, this is the documented default delivery path and materially weakens security posture.
   Minimum actionable fix: Make the default path require explicit secrets or clearly isolate demo bootstrap from normal delivery; disable bootstrap users unless explicitly opted in; move predictable credentials to a separate demo-only profile.

#### Medium

6. Severity: Medium
   Title: Drug create/update paths do not enforce the prompt’s input-validation and controlled-vocabulary expectations
   Conclusion: Partial Fail
   Evidence: `repo/app/services/drug_service.py:10`, `repo/app/services/drug_service.py:47`, `repo/app/services/drug_service.py:32`, `repo/app/api/drug_routes.py:36`, `repo/app/utils/validators.py:72`, `repo/app/models/drug.py:19`
   Impact: JSON drug creation/update can persist invalid `form` values, unvalidated NDCs, and silently dropped tags because the service layer does not use the available validators and does not reject unknown taxonomy values. This weakens data integrity for the knowledge base.
   Minimum actionable fix: Validate form/NDC/tag fields on create and update, reject unknown taxonomy tags instead of silently ignoring them, and add API/unit tests for invalid form/NDC/tag submissions.

7. Severity: Medium
   Title: JSON auth endpoints sit outside the HMAC/replay-protection boundary described by the prompt
   Conclusion: Partial Fail
   Evidence: `repo/app/api/auth_routes.py:28`, `repo/app/api/auth_routes.py:83`, `repo/app/api/auth_routes.py:112`, `repo/app/api/auth_routes.py:136`, `repo/app/api/middleware.py:23`
   Impact: Login, registration, logout, and password-change JSON flows are not decorated with `verify_hmac_signature`, so the repository does not uniformly satisfy the prompt’s “API requests are signed with HMAC and protected against replay” statement.
   Minimum actionable fix: Either extend signing/replay protection to non-page JSON auth endpoints or narrow/document the contract so only explicitly public browser form endpoints are unsigned.

8. Severity: Medium
   Title: Class creation does not explicitly validate missing dates before persistence
   Conclusion: Partial Fail
   Evidence: `repo/app/services/review_service.py:111`, `repo/app/models/training.py:14`, `repo/app/api/class_page_routes.py:42`, `repo/API_tests/test_page_flows.py:650`
   Impact: `create_training_class()` only validates type when `class_date` is present, even though the model requires a non-null date. The page flow therefore relies on downstream DB behavior and generic exception handling instead of explicit business validation.
   Minimum actionable fix: Validate `class_date` as required in the service or route layer and update tests to expect a user-facing validation error rather than a success-style redirect.

6. Security Review Summary

- Authentication entry points: Partial Pass
  - Evidence: `repo/app/api/auth_routes.py:28`, `repo/app/services/auth_service.py:91`, `repo/app/config.py:20`
  - Reasoning: Username/password auth, password-strength checks, login rate limiting, session cookies, and logout exist. JSON auth endpoints are not HMAC-protected, and open self-registration exists without strong org validation.

- Route-level authorization: Partial Pass
  - Evidence: `repo/app/utils/decorators.py:6`, `repo/app/api/listing_routes.py:38`, `repo/app/api/review_routes.py:35`, `repo/app/api/moderation_routes.py:28`
  - Reasoning: Many routes use `login_required`, `require_permission`, or explicit org-scope checks. The admin area is a major exception because route permissions are global and not org-scoped.

- Object-level authorization: Partial Pass
  - Evidence: `repo/app/api/listing_routes.py:65`, `repo/app/api/review_routes.py:14`, `repo/app/api/moderation_routes.py:20`
  - Reasoning: Listings, reviews, and moderation objects usually enforce same-org access. Admin object operations on users/org settings/temp grants are not object-scoped by org.

- Function-level authorization: Partial Pass
  - Evidence: `repo/app/services/review_service.py:74`, `repo/app/services/review_service.py:96`, `repo/app/services/listing_service.py:162`
  - Reasoning: Service functions often enforce creator/instructor/admin-only actions. Auto-flag moderation is inconsistent with edit restrictions because hidden reviews are not marked moderated.

- Tenant / user data isolation: Fail
  - Evidence: `repo/app/api/admin_routes.py:25`, `repo/app/api/page_routes.py:35`, `repo/app/api/listing_routes.py:64`, `repo/app/static/js/sw.js:208`
  - Reasoning: Cross-campus admin queries are global; listing JSON exposes sensitive data beyond masked UI rules; offline caching can retain authenticated content across auth boundaries.

- Admin / internal / debug protection: Partial Pass
  - Evidence: `repo/app/api/admin_routes.py:21`, `repo/app/api/page_routes.py:23`
  - Reasoning: Admin routes are permission/role guarded and no obvious debug endpoints were found, but admin protections are too coarse because they ignore org-unit scope.

7. Tests and Logging Review

- Unit tests: Partial Pass
  - Evidence: `repo/unit_tests/test_hmac_middleware.py:24`, `repo/unit_tests/test_listing_service.py:73`, `repo/unit_tests/test_review_service.py:57`, `repo/unit_tests/test_moderation_service.py:63`, `repo/unit_tests/test_backup_service.py:59`
  - Reasoning: Unit tests cover several core services and security helpers, especially HMAC, listing workflow, moderation deadlines, encryption, and backups. They do not cover the highest-risk gaps found in this audit, such as admin org scoping, API masking leakage, or auto-flag edit lock behavior.

- API / integration tests: Partial Pass
  - Evidence: `repo/API_tests/test_authorization.py:140`, `repo/API_tests/test_review_api.py:30`, `repo/API_tests/test_admin_api.py:4`, `repo/API_tests/test_hmac_integration.py:104`
  - Reasoning: Integration coverage exists for many happy-path and authorization scenarios. Coverage is materially incomplete around cross-org admin actions, API sensitive-data exposure, and auth-boundary behavior of offline caching.

- Logging categories / observability: Partial Pass
  - Evidence: `repo/app/services/audit_service.py:46`, `repo/app/__init__.py:160`, `repo/app/utils/decorators.py:63`
  - Reasoning: Audit logging is substantial and immutable, and some exception logging exists. Broader operational observability appears limited from static evidence; there is little sign of structured application logging beyond audits and exception handlers.

- Sensitive-data leakage risk in logs / responses: Partial Pass
  - Evidence: `repo/app/services/audit_service.py:9`, `repo/app/models/listing.py:84`, `repo/app/api/listing_routes.py:64`
  - Reasoning: Audit logs sanitize several sensitive keys before persistence, which is positive. Response-level leakage remains material because listing APIs expose decrypted addresses directly.

8. Test Coverage Assessment (Static Audit)

#### 8.1 Test Overview

- Unit tests exist under `repo/unit_tests/`: `repo/run_tests.sh:64`, `repo/unit_tests/test_hmac_middleware.py:24`
- API / integration tests exist under `repo/API_tests/`: `repo/run_tests.sh:72`, `repo/API_tests/conftest.py:9`
- E2E tests exist under `repo/e2e_tests/` and are optional: `repo/README.md:88`, `repo/run_tests.sh:80`, `repo/e2e_tests/conftest.py:21`
- Frameworks: `pytest`, `pytest-flask`, and optional Playwright-driven browser tests: `repo/requirements.txt:11`, `repo/requirements.txt:12`, `repo/run_tests.sh:78`
- Documentation provides test commands: `repo/README.md:77`, `repo/run_tests.sh:61`

#### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
| --- | --- | --- | --- | --- | --- |
| HMAC signing and replay protection on API routes | `repo/unit_tests/test_hmac_middleware.py:75`, `repo/API_tests/test_hmac_integration.py:104` | Duplicate nonce, timestamp window, bad signature, and HX bypass checks: `repo/unit_tests/test_hmac_middleware.py:178`, `repo/API_tests/test_hmac_integration.py:129` | sufficient | Auth JSON endpoints are not covered because they are outside this boundary | Add tests for any JSON auth endpoints that are expected to be signed |
| Listing org-scope and status authorization | `repo/API_tests/test_authorization.py:140`, `repo/API_tests/test_authorization.py:275`, `repo/unit_tests/test_listing_service.py:178` | Cross-org listing read/edit/status checks: `repo/API_tests/test_authorization.py:159`, `repo/API_tests/test_authorization.py:221`, `repo/API_tests/test_authorization.py:294` | basically covered | No test proves masked data is preserved on listing JSON APIs | Add API tests asserting non-privileged users receive masked listing fields |
| Review submission by verified attendees only, duplicate prevention | `repo/unit_tests/test_review_service.py:57`, `repo/API_tests/test_review_api.py:30` | Non-attendee denied and duplicate rejected: `repo/unit_tests/test_review_service.py:88`, `repo/API_tests/test_review_api.py:47` | basically covered | No test covers hidden auto-flagged review edit behavior | Add tests for update denial after auto-flagging |
| Moderation reporting and appeal deadlines | `repo/unit_tests/test_moderation_service.py:95`, `repo/unit_tests/test_moderation_service.py:136` | Appeal expiry and resolution deadline assertions: `repo/unit_tests/test_moderation_service.py:164`, `repo/unit_tests/test_moderation_service.py:180` | basically covered | Auto-flag state consistency is not tested | Add unit/API tests for auto-flag setting `is_moderated` and blocking edits |
| Backup encryption / restore validation | `repo/unit_tests/test_backup_service.py:59`, `repo/API_tests/test_admin_api.py:139` | Encrypted backup file, restore filename checks, admin-only restore: `repo/unit_tests/test_backup_service.py:73`, `repo/API_tests/test_admin_api.py:152` | basically covered | No live restore/worker schedule execution proof | Add integration tests for successful dry-run restore and scheduled job invocation if runtime testing becomes allowed |
| Offline queue and page availability | `repo/e2e_tests/test_e2e.py:215`, `repo/e2e_tests/test_e2e.py:262`, `repo/e2e_tests/test_e2e.py:348` | Queued 202 response, cached `/listings` availability, login-page cache clearing: `repo/e2e_tests/test_e2e.py:231`, `repo/e2e_tests/test_e2e.py:271`, `repo/e2e_tests/test_e2e.py:368` | insufficient | Tests normalize authenticated page caching and do not prove unauthorized offline access is blocked after cookie expiry/user switch | Add E2E tests for offline access after logout/session expiry asserting cached authenticated HTML is not readable |
| Sensitive-data masking for non-privileged users | `repo/API_tests/test_page_flows.py:693` | Page detail masking only: `repo/API_tests/test_page_flows.py:698`, `repo/API_tests/test_page_flows.py:706` | insufficient | JSON/API leakage is untested | Add API tests for masked vs unmasked serializers by role |
| Admin org-scope isolation | No direct tests found | Existing admin tests only check auth/role, not cross-org scope: `repo/API_tests/test_admin_api.py:4` | missing | Severe defects could ship while all current admin tests pass | Add API/page tests for cross-org user listing, role assignment, temp grants, and org-settings denial |
| Drug validation and controlled vocabulary enforcement | `repo/unit_tests/test_drug_service.py:135`, `repo/API_tests/test_drug_api.py:15` | Duplicate and CSV invalid form coverage: `repo/unit_tests/test_drug_service.py:148`, `repo/unit_tests/test_drug_service.py:156` | insufficient | Create/update invalid form/NDC/tag cases are untested | Add API and unit tests for invalid create/update payloads and unknown taxonomy tags |

#### 8.3 Security Coverage Audit

- Authentication: basically covered
  - Evidence: `repo/API_tests/test_auth_api.py:6`, `repo/unit_tests/test_auth_service.py:27`
  - Remaining risk: The suite does not meaningfully cover the prompt mismatch where JSON auth endpoints are unsigned.

- Route authorization: basically covered
  - Evidence: `repo/API_tests/test_authorization.py:140`, `repo/API_tests/test_authorization.py:315`, `repo/API_tests/test_hmac_integration.py:177`
  - Remaining risk: Coverage focuses on listings/classes and misses admin org-scope boundaries.

- Object-level authorization: basically covered
  - Evidence: `repo/API_tests/test_review_api.py:134`, `repo/API_tests/test_authorization.py:159`
  - Remaining risk: Admin user/org-setting/temp-grant objects are not exercised across org boundaries.

- Tenant / data isolation: insufficient
  - Evidence: `repo/API_tests/test_page_flows.py:549`, `repo/e2e_tests/test_e2e.py:280`
  - Remaining risk: Current tests check logout cache clearing and user switch UI, but not offline unauthorized reads from cached authenticated pages and not API-level masking leaks.

- Admin / internal protection: missing for org scope
  - Evidence: `repo/API_tests/test_admin_api.py:4`
  - Remaining risk: Severe cross-campus admin overreach could remain undetected because current admin tests assert only authenticated-role behavior.

#### 8.4 Final Coverage Judgment

- Partial Pass

Major risks that are covered:
- HMAC header validation and replay protection on `/api/*`
- Listing workflow/status transitions and several listing authorization paths
- Review creation, attendee verification, duplicate prevention, coach reply ownership
- Moderation deadlines and backup encryption/restore guardrails

Major uncovered risks that mean tests could still pass while severe defects remain:
- Cross-org admin data and privilege operations
- API response leakage of masked listing data
- Offline cache access after logout/session expiry/user switch
- Auto-flag moderation state consistency
- Validation gaps on JSON drug create/update paths

9. Final Notes

- This audit is static-only. No runtime claim in this report should be read as executed proof.
- The strongest remediation priorities are:
  - org-scope every admin read/write path
  - enforce masking consistently on API responses
  - redesign offline caching so authenticated pages are not readable after auth loss
  - make auto-flagged reviews non-editable through the same moderation state model as manual actions
  - remove insecure default bootstrap/secrets from the primary delivery path
