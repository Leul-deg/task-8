# Test Coverage & README Audit Report
**Project:** Clinical Operations Portal  
**Date:** 2026-04-16  
**Audit Type:** Static Inspection Only — no code executed  

---

# PART 1 — TEST COVERAGE AUDIT

---

## 1. Backend Endpoint Inventory

Total discovered: **93 endpoints** across 12 blueprints.

### Auth (`/auth`)
| # | Method | Path | Handler |
|---|--------|------|---------|
| 1 | GET | `/auth/login` | `login_page` |
| 2 | POST | `/auth/login` | `login` |
| 3 | GET | `/auth/register` | `register_page` |
| 4 | POST | `/auth/register` | `register` |
| 5 | POST | `/auth/logout` | `logout` |
| 6 | GET | `/auth/me` | `me` |
| 7 | POST | `/auth/change-password` | `change_pw` |

### Listings API (`/api/listings`)
| # | Method | Path |
|---|--------|------|
| 8 | GET | `/api/listings` |
| 9 | POST | `/api/listings` |
| 10 | GET | `/api/listings/<id>` |
| 11 | PUT | `/api/listings/<id>` |
| 12 | POST | `/api/listings/<id>/status` |
| 13 | GET | `/api/listings/<id>/preview` |

### Listings Pages (`/listings`)
| # | Method | Path |
|---|--------|------|
| 14 | GET | `/listings` |
| 15 | GET | `/listings/new` |
| 16 | POST | `/listings` |
| 17 | GET | `/listings/<id>` |
| 18 | GET | `/listings/<id>/edit` |
| 19 | POST | `/listings/<id>` |
| 20 | POST | `/listings/<id>/status` |
| 21 | GET | `/listings/<id>/preview` |

### Reviews API (`/api`)
| # | Method | Path |
|---|--------|------|
| 22 | GET | `/api/classes/<id>/reviews` |
| 23 | POST | `/api/classes/<id>/reviews` |
| 24 | GET | `/api/reviews/<id>` |
| 25 | PUT | `/api/reviews/<id>` |
| 26 | POST | `/api/reviews/<id>/reply` |
| 27 | PUT | `/api/replies/<id>` |

### Training Classes API (`/api/classes`)
| # | Method | Path |
|---|--------|------|
| 28 | GET | `/api/classes` |

### Training Classes Pages (`/classes`)
| # | Method | Path |
|---|--------|------|
| 29 | GET | `/classes` |
| 30 | GET | `/classes/new` |
| 31 | POST | `/classes` |
| 32 | GET | `/classes/<id>` |
| 33 | POST | `/classes/<id>/register` |
| 34 | POST | `/classes/<id>/attendance` |
| 35 | POST | `/classes/<id>/reviews` |
| 36 | POST | `/classes/<id>/reviews/<review_id>/reply` |

### Moderation API (`/api/moderation`)
| # | Method | Path |
|---|--------|------|
| 37 | GET | `/api/moderation/reports` |
| 38 | POST | `/api/moderation/reports` |
| 39 | POST | `/api/moderation/reports/<id>/hide` |
| 40 | POST | `/api/moderation/reports/<id>/restore` |
| 41 | POST | `/api/moderation/reports/<id>/finalize` |
| 42 | POST | `/api/moderation/appeals` |
| 43 | POST | `/api/moderation/appeals/<id>/resolve` |

### Moderation Pages (`/moderation`)
| # | Method | Path |
|---|--------|------|
| 44 | GET | `/moderation` |
| 45 | POST | `/moderation/reports/<id>/hide` |
| 46 | POST | `/moderation/reports/<id>/restore` |
| 47 | POST | `/moderation/reports/<id>/finalize` |
| 48 | POST | `/moderation/reports/<id>/appeal` |
| 49 | POST | `/moderation/appeals/<id>/resolve` |

### Drugs API (`/api/drugs`)
| # | Method | Path |
|---|--------|------|
| 50 | GET | `/api/drugs` |
| 51 | POST | `/api/drugs` |
| 52 | GET | `/api/drugs/<id>` |
| 53 | PUT | `/api/drugs/<id>` |
| 54 | POST | `/api/drugs/<id>/submit` |
| 55 | POST | `/api/drugs/<id>/approve` |
| 56 | POST | `/api/drugs/<id>/reject` |
| 57 | POST | `/api/drugs/import` |

### Drugs Pages (`/drugs`)
| # | Method | Path |
|---|--------|------|
| 58 | GET | `/drugs` |
| 59 | GET | `/drugs/new` |
| 60 | POST | `/drugs` |
| 61 | GET | `/drugs/<id>` |
| 62 | POST | `/drugs/<id>/submit` |
| 63 | POST | `/drugs/<id>/approve` |
| 64 | POST | `/drugs/<id>/reject` |
| 65 | GET | `/drugs/import` |
| 66 | POST | `/drugs/import` |

### Admin API (`/api/admin`)
| # | Method | Path |
|---|--------|------|
| 67 | GET | `/api/admin/users` |
| 68 | GET | `/api/admin/users/<id>` |
| 69 | POST | `/api/admin/users/<id>/roles` |
| 70 | DELETE | `/api/admin/users/<id>/roles/<name>` |
| 71 | POST | `/api/admin/users/<id>/temp-grants` |
| 72 | POST | `/api/admin/temp-grants/<id>/revoke` |
| 73 | GET | `/api/admin/org-units` |
| 74 | POST | `/api/admin/org-units` |
| 75 | GET | `/api/admin/org-units/<id>/settings` |
| 76 | PATCH | `/api/admin/org-units/<id>/settings` |
| 77 | GET | `/api/admin/audit-logs` |
| 78 | POST | `/api/admin/backup` |
| 79 | GET | `/api/admin/backups` |
| 80 | POST | `/api/admin/backups/restore` |
| 81 | GET | `/api/admin/permissions/audit` |

### Admin Pages (no prefix)
| # | Method | Path |
|---|--------|------|
| 82 | GET | `/dashboard` |
| 83 | GET | `/admin` |
| 84 | GET | `/admin/users` |
| 85 | POST | `/admin/users/<id>/roles` |
| 86 | GET | `/admin/org-settings` |
| 87 | POST | `/admin/org-settings/<id>` |
| 88 | GET | `/admin/backups` |
| 89 | POST | `/admin/backups/run` |
| 90 | POST | `/admin/backups/restore` |
| 91 | GET | `/admin/permissions/audit` |

### App Root
| # | Method | Path |
|---|--------|------|
| 92 | GET | `/` |
| 93 | GET | `/sw.js` |

---

## 2. API Test Mapping Table

| # | Endpoint | Covered | Test Type | Test File(s) | Evidence |
|---|----------|---------|-----------|--------------|---------|
| 1 | GET /auth/login | YES | True No-Mock HTTP | test_auth_api.py, test_page_flows.py | `test_login_page_reachable`, `test_login_page_renders` |
| 2 | POST /auth/login | YES | True No-Mock HTTP | test_auth_api.py, test_page_flows.py | `test_login_success`, `test_login_wrong_password`, `test_successful_login_redirects_to_dashboard` |
| 3 | GET /auth/register | YES | True No-Mock HTTP | test_auth_api.py | `test_register_success` (GET precedes POST in form flow) |
| 4 | POST /auth/register | YES | True No-Mock HTTP | test_auth_api.py | `test_register_success`, `test_register_duplicate_username`, `test_register_weak_password` |
| 5 | POST /auth/logout | YES | True No-Mock HTTP | test_auth_api.py, test_page_flows.py | `test_logout`, `test_logout_sets_no_store_cache_header`, `test_logout_clears_session` |
| 6 | GET /auth/me | YES | True No-Mock HTTP | test_auth_api.py | `test_me_authenticated`, `test_me_unauthenticated` |
| 7 | POST /auth/change-password | **NO** | — | — | No HTTP-level test found in any test file |
| 8 | GET /api/listings | YES | True No-Mock HTTP | test_listing_api.py | `test_list_listings` |
| 9 | POST /api/listings | YES | True No-Mock HTTP | test_listing_api.py | `test_create_listing` |
| 10 | GET /api/listings/<id> | YES | True No-Mock HTTP | test_listing_api.py, test_authorization.py | `test_get_listing`, `test_user_can_read_own_org_listing` |
| 11 | PUT /api/listings/<id> | YES | True No-Mock HTTP | test_listing_api.py | `test_update_listing` |
| 12 | POST /api/listings/<id>/status | YES | True No-Mock HTTP | test_listing_api.py, test_authorization.py | `test_update_listing_status`, `test_owner_org_can_change_status` |
| 13 | GET /api/listings/<id>/preview | **NO** | — | — | Page route `/listings/<id>/preview` covered but `/api/listings/<id>/preview` has no HTTP test |
| 14 | GET /listings | YES | True No-Mock HTTP | test_auth_api.py, test_frontend_components.py | `test_listings_nav_reachable`, `test_listing_grid_partial_renders_for_hx_request` |
| 15 | GET /listings/new | YES | True No-Mock HTTP | test_page_flows.py | `test_create_listing_form_post` (GET implied) |
| 16 | POST /listings | YES | True No-Mock HTTP | test_page_flows.py | `test_create_listing_form_post` |
| 17 | GET /listings/<id> | YES | True No-Mock HTTP | test_page_flows.py, test_authorization.py | `test_edit_form_renders_with_existing_data`, `test_page_detail_cross_org_denied` |
| 18 | GET /listings/<id>/edit | YES | True No-Mock HTTP | test_page_flows.py, test_authorization.py | `test_edit_form_renders_with_existing_data`, `test_owner_org_can_open_edit_form` |
| 19 | POST /listings/<id> | YES | True No-Mock HTTP | test_page_flows.py | `test_edit_form_post_saves_and_redirects` |
| 20 | POST /listings/<id>/status | YES | True No-Mock HTTP | test_page_flows.py, test_authorization.py | `test_status_change_htmx_returns_partial`, `test_owner_org_can_change_status_via_page` |
| 21 | GET /listings/<id>/preview | YES | True No-Mock HTTP | test_frontend_components.py | `test_listing_preview_partial_renders_modal_fragment` |
| 22 | GET /api/classes/<id>/reviews | YES | True No-Mock HTTP | test_review_api.py | `test_list_reviews` |
| 23 | POST /api/classes/<id>/reviews | YES | True No-Mock HTTP | test_review_api.py | `test_create_review`, `test_duplicate_review` |
| 24 | GET /api/reviews/<id> | YES | True No-Mock HTTP | test_review_api.py | `test_cross_org_user_denied_review_detail` |
| 25 | PUT /api/reviews/<id> | YES | True No-Mock HTTP | test_review_api.py | `test_cross_org_user_denied_review_update`, `test_same_org_non_author_update_returns_403` |
| 26 | POST /api/reviews/<id>/reply | YES | True No-Mock HTTP | test_review_api.py | `test_add_coach_reply` |
| 27 | PUT /api/replies/<id> | YES | True No-Mock HTTP | test_review_api.py | `test_update_reply` |
| 28 | GET /api/classes | YES | True No-Mock HTTP | test_page_flows.py, test_frontend_components.py | `test_class_list_api_returns_json`, `test_class_list_api_htmx_partial` |
| 29 | GET /classes | YES | True No-Mock HTTP | test_page_flows.py, test_authorization.py | `test_class_index_page_renders`, `test_class_list_requires_auth` |
| 30 | GET /classes/new | YES | True No-Mock HTTP | test_page_flows.py | `test_admin_can_access_new_class_form`, `test_staff_cannot_access_new_class_form` |
| 31 | POST /classes | YES | True No-Mock HTTP | test_page_flows.py | `test_admin_can_create_class`, `test_staff_cannot_create_class` |
| 32 | GET /classes/<id> | YES | True No-Mock HTTP | test_page_flows.py, test_authorization.py | `test_class_detail_renders`, `test_same_org_user_can_view_detail` |
| 33 | POST /classes/<id>/register | YES | True No-Mock HTTP | test_page_flows.py, test_authorization.py | `test_register_for_class`, `test_cross_org_user_cannot_register_for_class` |
| 34 | POST /classes/<id>/attendance | YES | True No-Mock HTTP | test_page_flows.py | `test_attendance_instructor_marks_attended`, `test_attendance_non_instructor_gets_flash_error` |
| 35 | POST /classes/<id>/reviews | YES | True No-Mock HTTP | test_page_flows.py | `test_class_review_page_duplicate_flashes_and_redirects` |
| 36 | POST /classes/<id>/reviews/<review_id>/reply | YES | True No-Mock HTTP | test_page_flows.py | `test_instructor_can_reply`, `test_non_instructor_cannot_reply` |
| 37 | GET /api/moderation/reports | **NO** | — | — | No list-reports API test in test_moderation_api.py |
| 38 | POST /api/moderation/reports | YES | True No-Mock HTTP | test_moderation_api.py | `test_report_review`, `test_report_requires_auth`, `test_cross_org_user_cannot_report_foreign_review` |
| 39 | POST /api/moderation/reports/<id>/hide | YES | True No-Mock HTTP | test_moderation_api.py | `test_hide_review`, `test_cross_org_moderator_cannot_hide_foreign_report` |
| 40 | POST /api/moderation/reports/<id>/restore | YES | True No-Mock HTTP | test_moderation_api.py | `test_restore_review` |
| 41 | POST /api/moderation/reports/<id>/finalize | **NO** | — | — | Page route covered (`test_finalize_report_htmx`), API route `/api/moderation/reports/<id>/finalize` has no HTTP test |
| 42 | POST /api/moderation/appeals | YES | True No-Mock HTTP | test_moderation_api.py | `test_file_appeal`, `test_non_author_appeal_returns_403` |
| 43 | POST /api/moderation/appeals/<id>/resolve | **NO** | — | — | Page route covered, API route `/api/moderation/appeals/<id>/resolve` has no HTTP test |
| 44 | GET /moderation | YES | True No-Mock HTTP | test_page_flows.py, test_frontend_components.py | `test_moderation_queue_renders`, `test_moderation_queue_htmx_returns_report_list_partial` |
| 45 | POST /moderation/reports/<id>/hide | YES | True No-Mock HTTP | test_page_flows.py, test_frontend_components.py | `test_hide_review_htmx_returns_updated_card`, `test_moderation_hide_htmx_returns_updated_card_fragment` |
| 46 | POST /moderation/reports/<id>/restore | YES | True No-Mock HTTP | test_page_flows.py | `test_restore_review_htmx_returns_updated_card` |
| 47 | POST /moderation/reports/<id>/finalize | YES | True No-Mock HTTP | test_page_flows.py | `test_finalize_report_htmx` |
| 48 | POST /moderation/reports/<id>/appeal | YES | True No-Mock HTTP | test_page_flows.py | `test_appeal_filed_by_review_author_redirects`, `test_appeal_creates_moderation_appeal_record` |
| 49 | POST /moderation/appeals/<id>/resolve | YES | True No-Mock HTTP | test_page_flows.py | `test_resolve_appeal_upheld_by_moderator`, `test_resolve_appeal_overturned_by_moderator`, `test_resolve_requires_moderator_permission` |
| 50 | GET /api/drugs | YES | True No-Mock HTTP | test_drug_api.py, test_frontend_components.py | `test_list_drugs`, `test_drug_results_api_htmx_partial` |
| 51 | POST /api/drugs | YES | True No-Mock HTTP | test_drug_api.py | `test_create_drug`, `test_create_drug_requires_auth`, `test_create_drug_rejects_invalid_form` |
| 52 | GET /api/drugs/<id> | YES | True No-Mock HTTP | test_drug_api.py | `test_get_drug`, `test_staff_cannot_view_draft_drug_by_id`, `test_admin_can_view_draft_drug_by_id` |
| 53 | PUT /api/drugs/<id> | PARTIAL | True No-Mock HTTP | test_drug_api.py | `test_update_drug_rejects_invalid_ndc` (failure path only; no success path test found) |
| 54 | POST /api/drugs/<id>/submit | YES | True No-Mock HTTP | test_drug_api.py | `test_approve_workflow`, `test_submit_for_approval_denied_for_non_editor_non_owner`, `test_submit_for_approval_allowed_for_creator` |
| 55 | POST /api/drugs/<id>/approve | YES | True No-Mock HTTP | test_drug_api.py | `test_approve_workflow` |
| 56 | POST /api/drugs/<id>/reject | YES | True No-Mock HTTP | test_drug_api.py | `test_reject_drug` |
| 57 | POST /api/drugs/import | YES | True No-Mock HTTP | test_drug_api.py | `test_bulk_import` |
| 58 | GET /drugs | YES | True No-Mock HTTP | test_auth_api.py, test_page_flows.py, test_frontend_components.py | `test_drugs_nav_reachable`, `test_drug_page_renders`, `test_drug_results_page_htmx_partial` |
| 59 | GET /drugs/new | YES | True No-Mock HTTP | test_page_flows.py | `test_drug_new_form_renders`, `test_drug_new_form_staff_forbidden` |
| 60 | POST /drugs | YES | True No-Mock HTTP | test_page_flows.py | `test_drug_submit_page` (creates drug then submits) |
| 61 | GET /drugs/<id> | YES | True No-Mock HTTP | test_page_flows.py | `test_drug_submit_page`, `test_staff_cannot_view_draft_drug_page` |
| 62 | POST /drugs/<id>/submit | YES | True No-Mock HTTP | test_page_flows.py | `test_drug_submit_page` |
| 63 | POST /drugs/<id>/approve | YES | True No-Mock HTTP | test_page_flows.py | `test_drug_approve_page` |
| 64 | POST /drugs/<id>/reject | YES | True No-Mock HTTP | test_page_flows.py | `test_drug_reject_page` |
| 65 | GET /drugs/import | YES | True No-Mock HTTP | test_page_flows.py | `test_drug_import_page_get` |
| 66 | POST /drugs/import | YES | True No-Mock HTTP | test_page_flows.py | `test_drug_import_page_post`, `test_drug_import_page_post_no_file` |
| 67 | GET /api/admin/users | YES | True No-Mock HTTP | test_admin_api.py, test_frontend_components.py | `test_list_users_as_admin`, `test_list_users_as_staff_forbidden`, `test_admin_users_api_htmx_partial` |
| 68 | GET /api/admin/users/<id> | YES | True No-Mock HTTP | test_admin_api.py | `test_get_user_by_id`, `test_get_user_by_id_out_of_scope_denied` |
| 69 | POST /api/admin/users/<id>/roles | YES | True No-Mock HTTP | test_admin_api.py | `test_assign_role`, `test_out_of_scope_user_role_assign_denied` |
| 70 | DELETE /api/admin/users/<id>/roles/<name> | YES | True No-Mock HTTP | test_admin_api.py | `test_delete_role`, `test_delete_role_out_of_scope_denied` |
| 71 | POST /api/admin/users/<id>/temp-grants | YES | True No-Mock HTTP | test_admin_api.py | `test_temp_grant`, `test_temp_grant_invalid_hours` |
| 72 | POST /api/admin/temp-grants/<id>/revoke | PARTIAL | True No-Mock HTTP | test_admin_api.py | `test_scoped_admin_cannot_revoke_out_of_scope_temp_grant` (negative scope test only; no success-path revoke test) |
| 73 | GET /api/admin/org-units | YES | True No-Mock HTTP | test_admin_api.py | `test_list_org_units`, `test_org_settings_reflected_in_list_orgs` |
| 74 | POST /api/admin/org-units | YES | True No-Mock HTTP | test_admin_api.py | `test_create_org_unit`, `test_create_org_unit_requires_permission` |
| 75 | GET /api/admin/org-units/<id>/settings | YES | True No-Mock HTTP | test_admin_api.py | `test_get_org_settings` |
| 76 | PATCH /api/admin/org-units/<id>/settings | YES | True No-Mock HTTP | test_admin_api.py | `test_update_org_settings_valid`, `test_update_org_settings_persists`, `test_update_org_settings_invalid_mode` |
| 77 | GET /api/admin/audit-logs | YES | True No-Mock HTTP | test_admin_api.py | `test_audit_logs`, `test_scoped_admin_audit_logs_filtered` |
| 78 | POST /api/admin/backup | YES | True No-Mock HTTP | test_backup_integration.py | `test_run_backup_creates_encrypted_file` |
| 79 | GET /api/admin/backups | YES | True No-Mock HTTP | test_backup_integration.py, test_admin_api.py | `test_list_backups_returns_created_file`, `test_list_backups_api` |
| 80 | POST /api/admin/backups/restore | YES | True No-Mock HTTP | test_backup_integration.py | `test_restore_dry_run_validates_backup`, `test_restore_full_returns_restored_status`, `test_restore_missing_file_returns_404` |
| 81 | GET /api/admin/permissions/audit | YES | True No-Mock HTTP | test_frontend_components.py, test_admin_api.py | `test_admin_api_permissions_audit_htmx_partial`, `test_scoped_admin_permission_audit_filtered` |
| 82 | GET /dashboard | YES | True No-Mock HTTP | test_page_flows.py | `test_dashboard_accessible_after_login` |
| 83 | GET /admin | YES | True No-Mock HTTP | test_page_flows.py | `test_admin_panel_renders`, `test_admin_panel_staff_forbidden` |
| 84 | GET /admin/users | YES | True No-Mock HTTP | test_page_flows.py | `test_admin_users_page_renders`, `test_admin_users_page_staff_forbidden` |
| 85 | POST /admin/users/<id>/roles | YES | True No-Mock HTTP | test_page_flows.py | `test_admin_assign_role_page` |
| 86 | GET /admin/org-settings | YES | True No-Mock HTTP | test_admin_api.py | `test_admin_org_settings_page_reachable` |
| 87 | POST /admin/org-settings/<id> | YES | True No-Mock HTTP | test_admin_api.py | `test_admin_org_settings_page_form_submit` |
| 88 | GET /admin/backups | YES | True No-Mock HTTP | test_admin_api.py, test_backup_integration.py | `test_admin_backups_page_reachable`, `test_admin_backups_page_renders` |
| 89 | POST /admin/backups/run | YES | True No-Mock HTTP | test_backup_integration.py, test_page_flows.py | `test_admin_run_backup_redirects_with_flash`, `test_admin_backups_run_admin_redirects` |
| 90 | POST /admin/backups/restore | YES | True No-Mock HTTP | test_backup_integration.py | `test_admin_backup_dry_run_page_route` |
| 91 | GET /admin/permissions/audit | YES | True No-Mock HTTP | test_page_flows.py, test_frontend_components.py | `test_admin_permissions_audit_page_renders`, `test_admin_permissions_audit_htmx_partial` |
| 92 | GET / | **NO** | — | — | Root redirect not directly tested; navigation tests start at `/listings`, `/dashboard`, etc. |
| 93 | GET /sw.js | **NO** | — | — | Service worker tested behaviourally via E2E, but direct `GET /sw.js` not explicitly asserted |

---

## 3. API Test Classification

**All HTTP tests in this project use the Flask test client with `create_app('testing')`, a real SQLite in-memory (or file-based) database, and no mocking of services or transport. All are classified True No-Mock HTTP.**

| Category | Count | Files |
|----------|-------|-------|
| True No-Mock HTTP | 273 | All API_tests/*.py (11 files) |
| HTTP with Mocking | 0 | — |
| Non-HTTP Unit Tests | ~195 | All unit_tests/*.py (12 files) |
| Browser E2E (Playwright) | 32 | e2e_tests/test_e2e.py |
| **Total** | **~500** | |

---

## 4. Mock Detection

**No mocking detected.** Grep analysis finds no `unittest.mock`, `pytest-mock`, `MagicMock`, `patch()`, `monkeypatch`, `dependency injection overrides`, or stubbed services across any test file.

All test fixtures use real app instances:
- `create_app('testing')` — real Flask app, real routes, real middleware
- `_db.create_all()` / `_db.drop_all()` — real SQLite schema
- `app.test_client()` — real HTTP dispatch through Werkzeug test client
- Business logic (services) executes end-to-end without interception

---

## 5. Coverage Summary

| Metric | Value |
|--------|-------|
| Total endpoints | 93 |
| Endpoints with HTTP tests (any coverage) | 86 |
| Endpoints with success-path HTTP tests | 84 |
| Endpoints uncovered | 5 (endpoints 7, 13, 37, 41, 43) |
| Endpoints partially covered (failure path only) | 2 (endpoints 53, 72) |
| Endpoints with root/infra only | 2 (endpoints 92, 93) |
| **HTTP Coverage %** | **92.5%** (86/93) |
| **True API Coverage %** | **92.5%** (same — no mocking) |

### Uncovered Endpoints (5)
| Endpoint | Reason |
|----------|--------|
| POST /auth/change-password | No HTTP test found in any test file |
| GET /api/listings/<id>/preview | API route distinct from `/listings/<id>/preview` page route; no API-level test |
| GET /api/moderation/reports | List endpoint has no test (only create/hide/restore tested via API) |
| POST /api/moderation/reports/<id>/finalize | API route not tested (page route `/moderation/reports/<id>/finalize` IS covered) |
| POST /api/moderation/appeals/<id>/resolve | API route not tested (page route `/moderation/appeals/<id>/resolve` IS covered) |

### Partially Covered Endpoints (2)
| Endpoint | Gap |
|----------|-----|
| PUT /api/drugs/<id> | Only failure path tested (`test_update_drug_rejects_invalid_ndc`); no 200 success path |
| POST /api/admin/temp-grants/<id>/revoke | Only cross-org denial tested; no success-path revoke |

---

## 6. Unit Test Summary

| Test File | Module Covered | Test Count | Key Assertions |
|-----------|---------------|------------|----------------|
| test_auth_service.py | `auth_service`, `LoginAttempt` | 22 | Register, login, password validation, rate-limiting (5 new tests), staff role assignment |
| test_audit_service.py | `audit_service` | 7 | Log creation, field masking, serialization |
| test_backup_service.py | `backup_service` | 15 | AES-GCM encryption, SQLite backup/restore, retention pruning |
| test_drug_service.py | `drug_service` | 16 | CRUD, approval workflow, FTS search, CSV import |
| test_encryption_service.py | `encryption_service`, `hmac_middleware` | 16 | AES-256-GCM roundtrip, HMAC sign/verify, model field encryption |
| test_hmac_middleware.py | `middleware.verify_hmac_signature` | 17 | All 14 HMAC validation paths (missing sig, expired, duplicate nonce, etc.) |
| test_listing_service.py | `listing_service` | 26 | Full FSM workflow, 12 validation edge cases, pagination, search |
| test_models.py | All ORM models | 15 | Relationships, password hashing, serialization, audit immutability |
| test_moderation_service.py | `moderation_service` | 18 | Keyword scan, report/hide/restore, appeal filing window, resolution |
| test_permission_service.py | `permission_service` | 15 | RBAC via role/temp-grant, org hierarchy traversal, listing-scope checks |
| test_queue_service.py | `queue_service` | 28 | Full job lifecycle: enqueue→claim→process→complete/retry/dead-letter |
| test_review_service.py | `review_service` | 13 | Review creation, coach replies, display modes, attendee enforcement |

### Modules NOT directly unit-tested
| Module | Status |
|--------|--------|
| `auth_routes.py` | Covered indirectly via API tests |
| `listing_routes.py` / `listing_page_routes.py` | Covered via API tests |
| `class_page_routes.py` / `class_routes.py` | Covered via API tests |
| `drug_routes.py` / `drug_page_routes.py` | Covered via API tests |
| `admin_routes.py` | Covered via API tests |
| `moderation_routes.py` / `moderation_page_routes.py` | Covered via API tests |
| `page_routes.py` | Covered via API tests |
| `config.py` | Partially covered by `test_encryption_service.py::test_create_app_fails_without_key_in_dev_mode` |

All core business logic modules are unit-tested. Route files are not unit-tested directly (correct practice — they are tested via integration tests).

---

## 7. API Observability Check

| Test File | Observability Quality |
|-----------|----------------------|
| test_listing_api.py | **STRONG** — asserts status codes, response JSON structure, field masking, status transitions |
| test_auth_api.py | **STRONG** — asserts 200/401/403, response body fields, cache headers |
| test_authorization.py | **STRONG** — asserts HTTP 403/404 for cross-org; 200 for in-scope; request inputs explicit |
| test_drug_api.py | **STRONG** — create/read/update/approve/reject paths; visibility rules verified |
| test_review_api.py | **STRONG** — reply permission, display mode, org scope, PUT success and failure |
| test_admin_api.py | **STRONG** — 40 tests covering user mgmt, org settings, audit, backups with real DB state checks |
| test_moderation_api.py | **MODERATE** — 8 tests for core paths; resolve/finalize API routes missing |
| test_frontend_components.py | **STRONG** — HTMX partial assertions: verifies no `<!DOCTYPE`, checks partial-specific DOM attributes |
| test_page_flows.py | **STRONG** — 84 tests; many verify DB state post-request (e.g., drug status, role assignment, appeal record) |
| test_hmac_integration.py | **STRONG** — tests all 14 distinct HMAC edge cases with explicit header/signature manipulation |
| test_backup_integration.py | **STRONG** — real file I/O; verifies `.enc` file exists, dry-run `{status:valid}`, full restore `{status:restored}` |

**Weak tests:** None identified. All test files exercise real request/response paths with meaningful assertions.

---

## 8. Test Quality & Sufficiency

### Success Paths
Covered for all major workflows: listing create/edit/publish, class create/attend/review, drug create/submit/approve/reject, moderation report/hide/restore/finalize/appeal, admin user/role/org management, backup/restore.

### Failure Cases
Thoroughly tested:
- 401 for unauthenticated access on every major endpoint type
- 403 for cross-org access attempts (39-test authorization suite)
- 400 for validation failures (listing 12 field validations, drug NDC/form, review rating/comment)
- 404 for missing resources
- 429 for rate-limit lockout (5 new rate-limiter tests)

### Edge Cases
- Rate limiter: N-1 failures (no lockout), N failures (lockout), success not counted
- Listing FSM: invalid transitions raise, lock→draft requires admin
- Appeal window: filing after 14-day deadline raises error
- HMAC: replay attack, expired timestamp, duplicate nonce all rejected
- Drug visibility: draft hidden from staff, visible to admin
- Address masking: staff gets `***`, admin gets full PII

### Auth/Permission Coverage
- `test_authorization.py` (39 tests): comprehensive org-scoped permission matrix
- `test_hmac_integration.py` (14 tests): all HMAC bypass paths closed
- Permission checks on all moderation, admin, and drug-approval routes

### Integration Boundaries
- `test_backup_integration.py` uses real on-disk SQLite — tests actual AES-GCM encrypt/decrypt I/O
- `e2e_tests/test_e2e.py` (32 tests) uses real Playwright/Chromium against live Werkzeug server — tests SW, IndexedDB, HTMX, offline caching

### `run_tests.sh` Analysis
- **Docker-based execution: YES** — prefers `docker compose exec` / `docker compose run`
- Falls back to local pytest only when Docker absent and `has_local_pytest` returns true
- **Coverage enforcement: YES** — runs `pytest --cov=app --cov-report=term-missing` with `.coveragerc` `fail_under=90`
- **E2E enforcement: YES** — E2E tests now fail loudly if Playwright/Chromium absent (fixed from silent skip)
- **No local-only dependency issues** — Docker is the default path

---

## 9. E2E Test Analysis

32 Playwright tests covering:
- Login/logout flows and session management
- Listing edit, status change, preview modal (HTMX partial swap)
- Moderation hide action (HTMX card swap)
- Offline SW behaviour: banner, queue, cache isolation
- Cache state on user switch and logout
- Coach reply enforcement (instructor vs. staff)
- **Drug lifecycle** (5 new tests): form render, create, submit-for-approval, approve, reject

**Limitation:** E2E tests require Playwright + Chromium installed in Docker image (now enforced via `playwright install --with-deps chromium` in Dockerfile). If the image is not rebuilt, they will fail at the `run_tests.sh` Playwright check.

---

## 10. Test Coverage Score

### Score: **91 / 100**

### Score Rationale

| Category | Max | Earned | Notes |
|----------|-----|--------|-------|
| Endpoint HTTP coverage (86/93 = 92.5%) | 30 | 27 | 5 uncovered + 2 partial |
| True No-Mock API tests | 15 | 15 | Zero mocking detected anywhere |
| Test depth (assertions, DB state, edge cases) | 20 | 18 | Deep assertions throughout; minor gap in PUT /api/drugs success path |
| Unit test completeness (12/12 service modules) | 15 | 15 | All services covered with meaningful tests |
| E2E / fullstack tests | 10 | 9 | 32 browser tests covering all major flows; drug lifecycle added |
| Coverage tooling & enforcement (fail_under=90) | 5 | 5 | .coveragerc + pytest-cov integrated into run_tests.sh |
| Test runner quality | 5 | 2 | run_tests.sh is Docker-first and enforces coverage; E2E now hard-fails if Playwright absent |

**Score: 91/100**

### Key Gaps Remaining

| Priority | Gap | Impact |
|----------|-----|--------|
| Medium | `POST /auth/change-password` — no HTTP test | Password change flow untestable without service-level workaround |
| Medium | `GET /api/moderation/reports` — list endpoint untested | Moderator dashboard data contract unverified at HTTP level |
| Medium | `POST /api/moderation/reports/<id>/finalize` and `POST /api/moderation/appeals/<id>/resolve` — API routes untested | Only page-route equivalents tested; API contract gaps for JSON consumers |
| Low | `PUT /api/drugs/<id>` — success path missing | Only validation failure tested; 200 response structure unverified |
| Low | `POST /api/admin/temp-grants/<id>/revoke` — success path missing | Only cross-org denial tested |
| Low | `GET /api/listings/<id>/preview` — API-layer route untested | Page-layer route covered; API route gap |

### Confidence & Assumptions
- **High confidence** on endpoint inventory (route files read directly, prefixes verified in `__init__.py` registration)
- **High confidence** on test mapping (test function names and imports read directly)
- **Assumption:** `GET /api/listings/<id>/preview` exists as a distinct route in `listing_routes.py` (blueprint `listing_bp`, prefix `/api/listings`); not read line-by-line but reported by Explore agent
- **Assumption:** `PUT /api/drugs/<id>` success test absent — inferred from test name inventory (no `test_update_drug_success` or equivalent)
- No runtime assumptions — all conclusions from static file inspection

---

---

# PART 2 — README AUDIT

---

## Project Type Detection

**Inferred type: Fullstack (Backend + HTMX frontend + Service Worker offline layer)**

README does not explicitly label the project type in a structured field, but the Tech Stack section clearly identifies: Flask backend, HTMX frontend, Docker Compose deployment. Applies fullstack standards.

---

## Hard Gate Results

| Gate | Status | Evidence |
|------|--------|---------|
| README exists at `repo/README.md` | ✅ PASS | 268-line file present |
| Clean markdown formatting | ✅ PASS | Valid markdown, headers, tables, code blocks |
| `docker compose up` startup instruction | ✅ PASS | Line 14: `` `docker compose up --build` `` |
| Access URL + port | ✅ PASS | Line 18: `Access: http://localhost:5000` |
| Verification method | ⚠️ PARTIAL | API tables present as documentation but no explicit curl/Postman example |
| No forbidden manual installs (Docker path) | ✅ PASS | Docker path requires only `docker compose up` |
| `pip install` in non-Docker section | ⚠️ NOTED | Present under "Local Development (without Docker)" — clearly labeled as optional path, not required for Docker |
| Demo credentials — username/password present | ❌ **FAIL** | Credentials NOT stated in README; README says only "temporary credentials are printed once in the container logs" — a reviewer cannot log in without running the app first |
| All roles documented | ✅ PASS | "Default Roles and Permissions" table lists 5 roles with permissions |

---

## Hard Gate Failures

### ❌ FAIL: Demo Credentials Missing from README

**Requirement:** If auth exists, README MUST provide username/email + password for all roles.

**Finding:** The README states:
> "When bootstrap demo users are enabled, temporary credentials are printed once in the container logs instead of using fixed defaults."

This is a **hard gate failure**. A reviewer, auditor, or new developer cannot:
- Know what credentials to use before running the app
- Verify whether credentials were generated at all
- Test the application without launching a container and reading its logs

The actual credentials used in all tests are `admin/admin123` (org_admin role) and `staffuser/staffpass` (staff role), but these credentials appear **nowhere** in the README.

**Impact:** Critical for evaluators. Any reviewer or new team member attempting to access the running application must read container logs rather than the README.

---

## High Priority Issues

### 1. Demo Credentials Absent (Hard Gate Failure — see above)
No credentials documented anywhere in the README. The "see container logs" approach is not compliant with documentation standards for a shared/reviewed project.

**Required fix:**
```
### Demo Credentials (development / local only)
| Role | Username | Password |
|------|----------|----------|
| org_admin | admin | admin123 |
| staff | staffuser | staffpass |
```
*Note: Document the actual seeded values or make them static defaults visible in `.env.example`.*

### 2. No Verification Example
**Finding:** The README documents API endpoints in tables but provides no `curl` or Postman example to confirm the system is working post-startup.

**Impact:** Reviewer cannot quickly validate the system without guessing auth headers and endpoint format.

**Required fix:**
```bash
# Verify the system is healthy after `docker compose up --build`
curl -s http://localhost:5000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -m json.tool
# Expected: {"id": 1, "username": "admin", ...}
```

---

## Medium Priority Issues

### 3. Endpoint Table Incomplete
The README's API endpoint tables omit several routes:
- `POST /api/admin/backups/restore` — not listed in Admin section
- `GET /api/moderation/reports` — not listed in Moderation section
- HTMX partial endpoints (`/api/admin/users` with `HX-Request`) — absent

**Impact:** Medium. The tables are labelled as documentation, not complete specs. Misleading for API consumers.

### 4. No Service Worker / Offline Capability Documentation
The README mentions "Offline-capable: service worker with stale-while-revalidate caching and queued writes" in the Features list but provides no:
- Description of which pages are cacheable
- Explanation of the write queue
- Notes for developers about SW behaviour during local dev

**Impact:** Medium. The offline capability is non-trivial (5+ business-day E2E tests cover it). New developers lack context.

### 5. E2E Test Prerequisite Not Clearly Stated
The README says: "E2E tests run only when Playwright and Chromium are installed; otherwise they are skipped without failing the suite."

This is now **incorrect** — per `run_tests.sh`, E2E tests hard-fail if Playwright/Chromium is absent. The Docker image (`Dockerfile`) now installs Playwright and Chromium, so in Docker the tests always run.

**Impact:** Medium. Misleading statement in README contradicts actual test behavior.

---

## Low Priority Issues

### 6. Recovery Procedure Manual Step
The Disaster Recovery section's restore procedure shows raw Python to decrypt backups:
```python
AESGCM(key).decrypt(raw[:12], raw[12:], None)
```
This is a manual out-of-band step. The `POST /api/admin/backups/restore` endpoint performs the same operation automatically. The manual procedure should note that the API-based restore is preferred and the Python snippet is a break-glass option only.

### 7. Missing HMAC Documentation for API Consumers
The README's API tables show endpoints but do not mention that all `/api/*` endpoints (except form-based login/logout) require HMAC-signed requests (`X-Signature`, `X-Timestamp`, `X-Nonce` headers). An external developer attempting to call the API would receive 400/401 responses with no README guidance on the signing requirement.

### 8. No Docker Health Check or Wait Instruction
`docker compose up --build` starts the application, but the README does not tell readers that the first boot may take 10–30 seconds before routes respond (database init, FTS5 setup, blueprint registration). A brief "wait for `Listening at: http://0.0.0.0:5000` in the logs" note would prevent false-start confusion.

---

## Engineering Quality Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Tech stack clarity | ✅ Excellent | Clear versions, no ambiguity |
| Architecture explanation | ✅ Good | Project structure tree with module descriptions |
| Testing instructions | ⚠️ Partial | `run_tests.sh` mentioned, no output format described; E2E description outdated |
| Security / roles documentation | ✅ Good | Role permission matrix present; HMAC/encryption noted in Security Notes |
| Workflows documented | ⚠️ Partial | Listing/drug approval workflows implied by status transitions; not explicitly documented |
| Disaster recovery | ✅ Good | RPO/RTO table, retention value, restore procedure |
| Production guidance | ✅ Good | `.env.example` reference, production compose profile, `ALLOW_DEFAULT_BOOTSTRAP_USERS=0` |
| Presentation quality | ✅ Good | Clean tables, code blocks, sensible section order |

---

## README Verdict: **PARTIAL PASS**

The README passes all structural and startup gates and provides strong architecture and operations documentation. It **fails** the demo credentials hard gate — the only way to log in is to read container logs, which is not acceptable for a documented project.

Fix the credentials gap and update the E2E test statement and the README qualifies for **PASS**.

---

# COMBINED SUMMARY

| Audit | Score / Verdict |
|-------|----------------|
| **Test Coverage & Sufficiency** | **91 / 100** |
| **README Quality & Compliance** | **PARTIAL PASS** |

**Blocker:** README demo credentials hard gate failure must be resolved before the README can pass.  
**Next test priority:** Cover `POST /auth/change-password`, `GET /api/moderation/reports`, and the two moderation API routes (`finalize`, `resolve-appeal`) to push test score above 93.
