# Clinical Ops Portal HTTP Reference

This document describes the server-rendered HTTP surface for the app in `repo/`.
It covers both browser/page routes and signed `/api/*` routes.

## Request model

- Page routes use session authentication plus CSRF-protected form posts.
- HTMX browser interactions use page routes and return HTML fragments when `HX-Request: true` is present.
- `/api/*` routes require:
  - a valid logged-in session
  - HMAC headers via `X-Signature`, `X-Timestamp`, and `X-Nonce`
- API routes return JSON unless explicitly documented as an HTMX fragment endpoint.
- Error handlers return HTML for page routes and JSON for API routes.

## Common status codes

- `200` success
- `201` resource created
- `400` validation failure / malformed request
- `401` authentication or missing-signature failure
- `403` permission or org-scope denial
- `404` missing resource
- `409` conflict, used by JSON registration when the username already exists
- `429` login rate limit exceeded

## Blueprint: Auth (`/auth`)

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/auth/login` | Public | None | HTML login page; redirects to `/dashboard` if already logged in | `200`, `302` |
| `GET` | `/auth/register` | Public | None | HTML registration page with active org units; redirects to `/dashboard` if already logged in | `200`, `302` |
| `POST` | `/auth/register` | Public | Form or JSON: `username`, `password`, optional `confirm_password` (form only), `email`, `full_name`, optional `org_unit_id` | Form: redirect to login on success, re-render HTML on failure. JSON: created user object | `201`, `302`, `400`, `409` |
| `POST` | `/auth/login` | Public | Form or JSON: `username`, `password` | Form: redirect to `/dashboard` on success, re-render login page on failure. JSON: current user | `200`, `302`, `401`, `429` |
| `POST` | `/auth/logout` | Logged-in user | None | JSON logout response; HTMX variant also emits `HX-Trigger: clearSwCache` | `200`, `401` |
| `GET` | `/auth/me` | Logged-in user | None | JSON current user | `200`, `401` |
| `POST` | `/auth/change-password` | Logged-in user | JSON: `old_password`, `new_password` | JSON message | `200`, `400`, `401` |

Notes:

- Logout sets `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`.
- Logout sets `Clear-Site-Data: "cache"`.
- HTMX logout is handled from the navbar and clears Service Worker caches/queue.

## Blueprint: Dashboard / Admin Pages (page routes, no prefix or `/admin`)

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/` | Public or logged-in | None | Redirect to `/dashboard` if authenticated, otherwise `/auth/login` | `302` |
| `GET` | `/dashboard` | Logged-in user | None | HTML dashboard page | `200`, `401` |
| `GET` | `/admin` | `org_admin` role | None | HTML admin landing page | `200`, `401`, `403` |
| `GET` | `/admin/users` | `org_admin` role | Query: optional `search` | HTML page; HTMX returns `admin/partials/user_table.html` | `200`, `401`, `403` |
| `POST` | `/admin/users/<user_id>/roles` | `org_admin` role | Form: `role_name` | Redirect back to users page; HTMX returns updated user-row fragment | `200`, `302`, `401`, `403`, `404` |
| `GET` | `/admin/org-settings` | `org_admin` role | None | HTML org settings page | `200`, `401`, `403` |
| `POST` | `/admin/org-settings/<org_id>` | `org_admin` role | Form: `reviewer_display_mode` | Redirect to org settings with flash message | `302`, `401`, `403`, `404` |
| `GET` | `/admin/permissions/audit` | `org_admin` role | Query: optional `start_date`, `end_date`, optional `format=csv` | HTML page, HTMX audit-table fragment, or CSV download | `200`, `401`, `403` |

## Blueprint: Listings Pages (`/listings`)

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/listings` | Logged-in user; org-scoped | Query: optional `status`, `search`, `page`, `per_page` | HTML listings page; HTMX returns `listings/partials/listing_grid.html` | `200`, `401` |
| `GET` | `/listings/new` | `listing.create` permission | None | HTML listing form | `200`, `401`, `403` |
| `POST` | `/listings` | `listing.create` permission | Form: `title`, address fields, `city`, `state`, `zip_code`, `floor_plan_notes`, `square_footage`, `monthly_rent`, `deposit`, `lease_start`, `lease_end`, `org_unit_id`, repeated `amenities` | Redirect to listing detail on success; re-render form with errors on failure | `302`, `400`, `401`, `403` |
| `GET` | `/listings/<listing_id>` | Logged-in user with org access | None | HTML listing detail page | `200`, `401`, `403`, `404` |
| `GET` | `/listings/<listing_id>/edit` | `listing.edit` permission scoped to listing org; listing must be `draft` or `unpublished` | None | HTML edit form or redirect with flash if status is non-editable | `200`, `302`, `401`, `403`, `404` |
| `POST` | `/listings/<listing_id>` | `listing.edit` permission scoped to listing org; listing must be `draft` or `unpublished` | Same form fields as create | Redirect to detail on success; re-render form on validation error | `302`, `400`, `401`, `403`, `404` |
| `POST` | `/listings/<listing_id>/status` | `listing.publish` permission scoped to listing org | Form: `status`, optional `reason` | Redirect to detail; HTMX returns `listings/partials/status_section.html` | `200`, `302`, `400`, `401`, `403`, `404` |
| `GET` | `/listings/<listing_id>/preview` | Logged-in user | None | HTML preview modal fragment | `200`, `401`, `404` |

## Blueprint: Listings API (`/api/listings`)

All endpoints in this section require session auth plus HMAC headers.

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/api/listings` | Logged-in user; org-scoped | Query: optional `org_unit_id`, `status`, `search`, `page`, `per_page` | JSON listing array; HTMX callers may receive `listings/partials/listing_grid.html` | `200`, `401`, `403` |
| `POST` | `/api/listings` | `listing.create` permission | JSON listing payload matching page create semantics | JSON listing object | `201`, `400`, `401`, `403` |
| `GET` | `/api/listings/<listing_id>` | Logged-in user with org access | None | JSON listing | `200`, `401`, `403`, `404` |
| `PUT` | `/api/listings/<listing_id>` | `listing.edit` permission scoped to listing org | JSON partial update payload | JSON listing | `200`, `400`, `401`, `403`, `404` |
| `POST` | `/api/listings/<listing_id>/status` | `listing.publish` permission scoped to listing org | JSON: `status`, optional `reason`; HTMX callers may submit form fields | JSON listing or HTMX status fragment | `200`, `400`, `401`, `403`, `404` |
| `GET` | `/api/listings/<listing_id>/preview` | Logged-in user with org access | None | HTML preview modal fragment | `200`, `401`, `403`, `404` |

## Blueprint: Classes Pages (`/classes`)

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/classes` | Logged-in user; org-scoped | Query: optional `search` | HTML classes index; HTMX returns `classes/partials/class_list.html` | `200`, `401` |
| `GET` | `/classes/new` | `class.create` permission | None | HTML class form | `200`, `401`, `403` |
| `POST` | `/classes` | `class.create` permission and org access | Form: `title`, `description`, `class_date`, `location`, `max_attendees`, `org_unit_id` | Redirect to class detail on success; redirect back with flash on error | `302`, `401`, `403` |
| `GET` | `/classes/<class_id>` | Logged-in user with org access | None | HTML class detail page with attendee/review state | `200`, `401`, `403`, `404` |
| `POST` | `/classes/<class_id>/register` | Logged-in user | None | Redirect to class detail with flash | `302`, `401`, `404` |
| `POST` | `/classes/<class_id>/attendance` | Logged-in user; service enforces instructor-only | Form: repeated `attended_users` | Redirect to class detail with flash | `302`, `401`, `404` |
| `POST` | `/classes/<class_id>/reviews` | Logged-in user; service enforces verified attendee rule | Form: `rating`, repeated `tags`, optional `comment` | Redirect to class detail with flash | `302`, `401`, `404` |
| `POST` | `/classes/<class_id>/reviews/<review_id>/reply` | Logged-in user; requires `review.reply` and must be class instructor | Form: `body` | Redirect to class detail with flash | `302`, `401`, `403`, `404` |

## Blueprint: Classes API (`/api/classes`)

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/api/classes` | Logged-in user; org-scoped; HMAC required | Query: optional `search` | JSON class array; HTMX callers may receive `classes/partials/class_list.html` | `200`, `401`, `403` |

## Blueprint: Reviews API (`/api`)

All endpoints here require session auth plus HMAC headers.

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/api/classes/<class_id>/reviews` | Logged-in user with org access | None | JSON reviews array with `reviewer_display` and optional `coach_reply` | `200`, `401`, `403`, `404` |
| `POST` | `/api/classes/<class_id>/reviews` | `review.create` permission; class org access; verified attendee required | JSON: `rating`, optional `comment`, optional `tags` | JSON review | `201`, `400`, `401`, `403`, `404` |
| `GET` | `/api/reviews/<review_id>` | Logged-in user with org access | None | JSON review | `200`, `401`, `403`, `404` |
| `PUT` | `/api/reviews/<review_id>` | Logged-in user with org access; service enforces author-only | JSON partial update: `rating`, `comment`, `tags` | JSON updated review | `200`, `400`, `401`, `403`, `404` |
| `POST` | `/api/reviews/<review_id>/reply` | `review.reply` permission; service enforces instructor-only | JSON: `body` | JSON coach reply | `201`, `400`, `401`, `403`, `404` |
| `PUT` | `/api/replies/<reply_id>` | `review.reply` permission; service enforces reply owner | JSON: `body` | JSON updated reply | `200`, `400`, `401`, `403`, `404` |

## Blueprint: Moderation Pages (`/moderation`)

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/moderation` | `review.moderate` permission | Query: optional `status` | HTML moderation queue; HTMX returns `moderation/partials/report_list.html` | `200`, `401`, `403` |
| `POST` | `/moderation/reports/<report_id>/hide` | `review.moderate` permission | Form: optional `reason` | Redirect to queue; HTMX returns updated `report_card` fragment | `200`, `302`, `401`, `403`, `404` |
| `POST` | `/moderation/reports/<report_id>/restore` | `review.moderate` permission | None | Redirect to queue; HTMX returns updated `report_card` fragment | `200`, `302`, `401`, `403`, `404` |
| `POST` | `/moderation/reports/<report_id>/finalize` | `review.moderate` permission | None | Redirect to queue; HTMX returns updated `report_card` fragment | `200`, `302`, `401`, `403`, `404` |
| `POST` | `/moderation/reports/<report_id>/appeal` | Logged-in user; service enforces report author and hidden-review rule | Form: `appeal_text` | Redirect to queue with flash | `302`, `401`, `403`, `404` |
| `POST` | `/moderation/appeals/<appeal_id>/resolve` | `review.moderate` permission | Form: `decision`, optional `notes` | Redirect to queue with flash | `302`, `400`, `401`, `403`, `404` |

## Blueprint: Moderation API (`/api/moderation`)

All endpoints here require session auth plus HMAC headers.

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/api/moderation/reports` | `review.moderate` permission | Query: optional `status` | JSON reports array; HTMX callers may receive `moderation/partials/report_list.html` | `200`, `401`, `403` |
| `POST` | `/api/moderation/reports` | Logged-in user | JSON: `review_id`, `reason`, optional `keyword_matches` | JSON moderation report | `201`, `400`, `401`, `404` |
| `POST` | `/api/moderation/reports/<report_id>/hide` | `review.moderate` permission | JSON or form: optional `reason` | JSON report or HTMX `report_card` fragment | `200`, `401`, `403`, `404` |
| `POST` | `/api/moderation/reports/<report_id>/restore` | `review.moderate` permission | None | JSON report or HTMX `report_card` fragment | `200`, `401`, `403`, `404` |
| `POST` | `/api/moderation/reports/<report_id>/finalize` | `review.moderate` permission | None | JSON report or HTMX `report_card` fragment | `200`, `401`, `403`, `404` |
| `POST` | `/api/moderation/appeals` | Logged-in user; service enforces author-only and hidden-review rule | JSON: `report_id`, `appeal_text` | JSON appeal | `201`, `400`, `401`, `403`, `404` |
| `POST` | `/api/moderation/appeals/<appeal_id>/resolve` | `review.moderate` permission | JSON: `decision`, optional `notes` | JSON resolved appeal | `200`, `400`, `401`, `403`, `404` |

## Blueprint: Drugs Pages (`/drugs`)

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/drugs` | Logged-in user | Query: optional `q`, `form`, `status`, `page` | HTML drug index; HTMX returns `drugs/partials/drug_results.html` | `200`, `401` |
| `GET` | `/drugs/new` | `drug.create` permission | None | HTML drug form | `200`, `401`, `403` |
| `POST` | `/drugs` | `drug.create` permission | Form: `generic_name`, `brand_name`, `strength`, `form`, `ndc_code`, `description`, `contraindications`, `side_effects` | Redirect to detail on success; re-render form on validation error | `302`, `200`, `401`, `403` |
| `GET` | `/drugs/<drug_id>` | Logged-in user; non-approved drugs visible only to `drug.approve` / `drug.edit` users | None | HTML drug detail | `200`, `401`, `403`, `404` |
| `POST` | `/drugs/<drug_id>/submit` | Logged-in user | None | Redirect to detail with flash | `302`, `401`, `404` |
| `POST` | `/drugs/<drug_id>/approve` | `drug.approve` permission | None | Redirect to detail with flash | `302`, `400`, `401`, `403`, `404` |
| `POST` | `/drugs/<drug_id>/reject` | `drug.approve` permission | Form: `reason` | Redirect to detail with flash | `302`, `400`, `401`, `403`, `404` |
| `GET` / `POST` | `/drugs/import` | `drug.import` permission | GET none; POST multipart field `csv_file` | HTML import page / import result page | `200`, `401`, `403` |

## Blueprint: Drugs API (`/api/drugs`)

All endpoints here require session auth plus HMAC headers.

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/api/drugs` | Logged-in user; non-approved filters restricted to `drug.approve` / `drug.edit` users | Query: optional `q`, `form`, `status`, `page`, `per_page` | JSON drug array; HTMX callers may receive `drugs/partials/drug_results.html` | `200`, `401` |
| `POST` | `/api/drugs` | `drug.create` permission | JSON drug payload | JSON drug | `201`, `400`, `401`, `403` |
| `GET` | `/api/drugs/<drug_id>` | Logged-in user; non-approved drugs restricted to privileged users | None | JSON drug | `200`, `401`, `403`, `404` |
| `PUT` | `/api/drugs/<drug_id>` | `drug.edit` permission | JSON partial update | JSON drug | `200`, `400`, `401`, `403`, `404` |
| `POST` | `/api/drugs/<drug_id>/submit` | Logged-in user | None | JSON drug | `200`, `400`, `401`, `404` |
| `POST` | `/api/drugs/<drug_id>/approve` | `drug.approve` permission | None | JSON drug | `200`, `400`, `401`, `403`, `404` |
| `POST` | `/api/drugs/<drug_id>/reject` | `drug.approve` permission | JSON: `reason` | JSON drug | `200`, `400`, `401`, `403`, `404` |
| `POST` | `/api/drugs/import` | `drug.import` permission | Multipart field `file` | JSON import summary | `200`, `400`, `401`, `403` |

## Blueprint: Admin API (`/api/admin`)

All endpoints here require session auth plus HMAC headers.

| Method | URL | Auth / role | Request params | Response | Status codes |
|---|---|---|---|---|---|
| `GET` | `/api/admin/users` | `admin.users` permission | Query: optional `search` | JSON users array; HTMX callers may receive `admin/partials/user_table.html` | `200`, `401`, `403` |
| `GET` | `/api/admin/users/<user_id>` | `admin.users` permission | None | JSON user | `200`, `401`, `403`, `404` |
| `POST` | `/api/admin/users/<user_id>/roles` | `admin.roles` permission | JSON: `role`; HTMX form: `role_name` | JSON user or updated user-row fragment | `200`, `401`, `403`, `404` |
| `DELETE` | `/api/admin/users/<user_id>/roles/<role_name>` | `admin.roles` permission | None | JSON user | `200`, `400`, `401`, `403`, `404` |
| `POST` | `/api/admin/users/<user_id>/temp-grants` | `permission.grant` permission | JSON: `permission`, optional `hours`, required `reason` | JSON temp grant | `201`, `400`, `401`, `403`, `404` |
| `POST` | `/api/admin/temp-grants/<grant_id>/revoke` | `permission.grant` permission | None | JSON revoked grant | `200`, `401`, `403`, `404` |
| `GET` | `/api/admin/org-units` | `admin.org_units` permission | None | JSON org units | `200`, `401`, `403` |
| `POST` | `/api/admin/org-units` | `admin.org_units` permission | JSON: `name`, `code`, `level`, optional `parent_id` | JSON org unit | `201`, `401`, `403`, `404` |
| `GET` | `/api/admin/org-units/<org_id>/settings` | `admin.org_units` permission | None | JSON `{ reviewer_display_mode }` | `200`, `401`, `403`, `404` |
| `PATCH` | `/api/admin/org-units/<org_id>/settings` | `admin.org_units` permission | JSON: `reviewer_display_mode` | JSON updated setting | `200`, `400`, `401`, `403`, `404` |
| `GET` | `/api/admin/audit-logs` | `admin.audit_log` permission | Query: optional `resource_type`, `resource_id`, `user_id`, `action`, `limit`, `offset` | JSON audit log list | `200`, `401`, `403` |
| `POST` | `/api/admin/backup` | `admin.backup` permission | None | JSON `{ backup_path }` | `200`, `401`, `403`, `500` |
| `GET` | `/api/admin/backups` | `admin.backup` permission | None | JSON backup file list | `200`, `401`, `403` |
| `POST` | `/api/admin/backups/restore` | `admin.backup` permission | JSON: required `filename`, optional `dry_run` | JSON restore or validation result | `200`, `400`, `401`, `403`, `404`, `500` |
| `GET` | `/api/admin/permissions/audit` | `org_admin` role | Query: optional `start_date`, `end_date`, optional `format=csv` | JSON entries, CSV download, or HTMX audit-table fragment | `200`, `401`, `403` |

## Unsupported / not present

The current app does not expose separate blueprints for booking, staff, analytics, or content-version APIs under those names. Their responsibilities are instead represented by:

- listings + classes for operational workflows
- drugs for knowledge-base content
- moderation + reviews for feedback governance
- admin + pages for user, org, audit, and backup operations
