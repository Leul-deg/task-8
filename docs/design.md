# Clinical Ops Portal Design Notes

This document explains why the application in `repo/` is structured the way it is and how its main architectural decisions fit together.

## 1. Overall architecture

The app uses a classic Flask application-factory pattern:

- `app/__init__.py` builds the app instance from a named config profile
- `app/extensions.py` owns extension singletons
- `app/api/*.py` defines HTTP entry points
- `app/services/*.py` holds business rules
- `app/models/*.py` owns persistence and serialization
- templates and static assets provide the server-rendered UI

This separation keeps the route layer thin:

- routes parse request data, enforce transport/auth decorators, and choose HTML vs JSON
- services implement validation and state transitions
- models stay focused on schema and `to_dict()` output

That pattern matters in this project because many workflows are available through both page routes and signed API routes. Sharing service logic avoids duplicated rules between those surfaces.

## 2. App factory decisions

The factory does more than just create Flask:

- loads config from `config_map`
- initializes SQLAlchemy, Flask-Login, and CSRF
- validates encryption configuration outside test mode
- registers all page and API blueprints
- installs HTML/JSON-aware error handlers
- injects request-scoped metadata like `request_id`
- expires temporary grants on each request
- sets no-store headers for authenticated traffic
- exposes the service worker from `/sw.js`

### Why the factory validates encryption up front

The app now raises at startup if `ENCRYPTION_KEY` is missing outside testing. That is deliberate:

- it avoids silent plaintext storage
- it keeps backup encryption and field encryption aligned
- it shifts failure to startup time instead of producing partially secure runtime behavior

## 3. Blueprint layout

The HTTP surface is split by both domain and interaction style:

- `auth_routes.py` mixes auth pages and auth handlers
- `page_routes.py` handles dashboard and admin pages
- `listing_page_routes.py`, `class_page_routes.py`, `moderation_page_routes.py`, `drug_page_routes.py` are browser-first page flows
- `listing_routes.py`, `class_routes.py`, `review_routes.py`, `moderation_routes.py`, `drug_routes.py`, `admin_routes.py` are signed `/api/*` routes

### Why page routes and API routes both exist

This split became important after HMAC enforcement was tightened:

- `/api/*` is the signed, machine-facing surface
- browser HTMX traffic uses page routes with session auth + CSRF

That prevents a fragile browser-signing dependency while still satisfying the “API requests are signed” requirement.

## 4. HTMX integration model

HTMX is used as progressive enhancement, not as a full SPA transport.

### Pattern

Each domain page route supports two response styles:

- normal browser request -> full HTML page
- `HX-Request: true` -> fragment-only partial

Examples:

- listings index returns `listings/partials/listing_grid.html`
- moderation queue returns `moderation/partials/report_list.html`
- status changes and modal previews return fragment-only partials

### Why this design was chosen

- avoids duplicating frontend state logic in JavaScript
- preserves server-rendered templates as the single view source of truth
- keeps browser interactions resilient on older workstations
- allows the same business rules to back both full-page and partial updates

### Swap-target conventions

The app uses explicit swap targets like:

- `#listing-grid`
- `#status-section`
- `#modal-container`
- `#report-list`
- `#report-<id>`

Those stable DOM anchors make E2E and page-flow tests much less brittle.

## 5. Authentication and transport security

There are two distinct trust models.

### Browser/page trust model

- Flask session cookie
- CSRF token on form posts
- no-store cache headers on authenticated responses
- logout-triggered cache and queue clearing

### Signed API trust model

- session authentication still required
- HMAC signature required on `/api/*`
- replay protection via timestamp + nonce
- 5-minute default acceptance window

### Why both exist

The app needs secure server-rendered browser flows and also a formally signed API layer. Trying to force all browser HTMX interactions through signed `/api/*` proved operationally brittle, so the app settled on a clear split instead of a mixed model.

## 6. Organization scope and RBAC

Permissions are not checked only at the role level; they are also scope-aware.

### Key design choices

- roles grant feature access
- temp grants can add time-limited access with required reason text
- permission checks optionally take `org_unit_id`
- parent org membership grants access to descendants

This solves a common operational problem: campus or department leaders need visibility across child units without duplicate assignments everywhere.

### Why page routes also enforce scope

The app does not assume that if an index is scoped, detail pages are safe by default. Individual page and API routes re-check object scope so a copied URL cannot bypass org filtering.

## 7. Listing lifecycle design

Listings implement an explicit status machine:

- `draft`
- `pending_review`
- `published`
- `unpublished`
- `expired`
- `locked`

The transition table lives in `listing_service.py`.

### Why a service-layer state machine was used

- all transitions are centralized
- validation is not duplicated between page routes and API routes
- audit history can be written consistently
- business-only rules stay separate from transport concerns

Examples of embedded policy:

- unpublish requires a reason
- publishing requires core completeness
- unlocking from `locked` back to `draft` is org-admin-only

### Why status history is first-class

Status changes are persisted in `ListingStatusHistory`, not inferred from audit logs alone. That makes the UI’s status-history panel cheap to render and easier to reason about.

## 8. Training and review workflow

Training classes and reviews are designed around verified attendance.

### Review eligibility

The app only accepts reviews from attendees with `attended=True`.

That decision was chosen because:

- registration alone is not proof of attendance
- review integrity matters for moderation and coach replies
- it creates a clear “verified attendee” rule in data, not just in UI wording

### Coach reply model

- one reply per review
- reply requires `review.reply`
- the instructor must also own the class

This dual check is deliberate: role-based access alone was too broad.

## 9. Reviewer identity display

Reviewer display mode is an org-unit policy:

- `full_name`
- `initials`
- `anonymous`

### Why org-level configuration was chosen

Classes belong to org units, and the privacy preference is best treated as a unit-level governance decision rather than a global environment knob.

The rendering layer reads that setting in both:

- page flows
- API review-list responses

That avoids drift between HTML and JSON views of the same review data.

## 10. Moderation and appeal workflow

Moderation combines automatic detection and manual action.

### Auto-flagging

Reviews are scanned against a small offline keyword blocklist. Matches:

- hide the review
- create a pending moderation report
- store matched keywords on the report

### Manual moderation

Moderators can:

- hide
- restore
- finalize

### Appeal workflow

Appeals may be filed only when:

- the review is hidden
- the caller is the original review author
- the appeal is filed inside the 14-day window

Resolution has two outcomes:

- `upheld`
- `overturned`

If overturned, the review is restored automatically.

### Why the appeal timing is computed this way

The filing deadline is anchored to the moderation resolution timestamp, while the resolution deadline is based on business days from filing. That matches the product requirement without relying on ambiguous UI-only timestamps.

## 11. Drug knowledge-base design

The drug subsystem is closer to editorial content management than raw CRUD.

### Key decisions

- duplicate detection uses `(generic_name, strength, form)`
- full-text search uses SQLite FTS5
- visibility is approval-gated
- non-approved content is visible only to privileged editorial roles

### Why approved-only visibility matters

This app treats drug records as governed knowledge-base content, not draft notes. Ordinary staff should not see draft or pending items because those may be incomplete or unapproved clinical content.

## 12. Offline-first design

The offline strategy is intentionally narrow and safe.

### What is cached

- static assets only

### What is not cached

- authenticated pages
- API responses

### Why

The app is intended for shared clinic workstations. Caching authenticated HTML or JSON would create a real cross-user exposure risk.

### Write-intent queue

The Service Worker stores failed non-GET requests in IndexedDB, then replays them:

- on Background Sync
- on reconnect fallback from the page

### Replay policy

- `2xx` -> remove from queue
- `4xx` -> mark failed and notify user
- network error / `5xx` -> leave pending for later retry

This policy is deliberate: invalid requests should not loop forever, but transient failures should still be retried.

## 13. Backup and restore design

Backups are implemented as encrypted SQLite copies.

### Backup flow

1. copy the SQLite database
2. encrypt the copy with AES-GCM
3. delete the plaintext intermediate file
4. prune old backups by retention window

### Restore flow

Restore supports a `dry_run` mode that:

- decrypts the file
- writes a temporary restore candidate
- runs `PRAGMA integrity_check`
- returns validation status without overwriting the active DB

### Why dry-run exists

The prompt requires testable restore behavior from the admin console. Dry-run provides a safe operational check without forcing an immediate production restore.

## 14. Data retention and auditability

The app separates retention behavior by data class.

### Explicit retention behavior

- backup files are pruned by `BACKUP_RETENTION_DAYS`
- temp grants are expired automatically
- queue entries remain until completed, failed, or manually cleared on logout

### Audit strategy

Critical changes are written to `AuditLog` as append-only records. The model intentionally does not expose update/delete behavior.

That design supports:

- compliance reporting
- operational debugging
- less ambiguous historical reconstruction than mutable log rows

## 15. Sensitive-field masking

The app uses a role-aware masking layer in template filters.

### Policy

- `org_admin` and `property_manager` can see operationally necessary detail
- less privileged users see initials or partial masking for names, emails, and addresses

### Why templated masking instead of controller-only masking

Because the app is server-rendered, placing masking logic in the template filter keeps the rule close to final presentation and reduces the risk of one template forgetting to apply a serializer transformation.

## 16. Queue service and background jobs

The internal `JobQueue` and `queue_service.py` provide lightweight asynchronous processing with retry/backoff.

### Registered handlers today

- `expire_listings`
- `expire_grants`

### Why a SQLite-backed queue was chosen

- no external infrastructure dependency
- easy to run locally and in small on-prem deployments
- aligns with the app’s overall SQLite-first operational model

### Retry strategy

Retries use exponential backoff with jitter and eventually move jobs to `dead_letter`.

## 17. Notes on requested topics not present in this codebase

Some requested design topics from the broader company guidance do not map to this specific repository:

- credit scoring algorithm
- analytics dwell-time heartbeat tracking
- feature-flag canary logic
- booking / waitlist auto-promotion
- content versioning lifecycle

Those concepts are not implemented in this Clinical Ops Portal codebase, so they are intentionally not described here as if they existed.
