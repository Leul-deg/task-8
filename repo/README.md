# Clinical Operations Portal

A Flask + SQLite + HTMX web application for managing internal property listings, clinical training classes, and drug knowledge base for a multi-campus healthcare organization.

## Tech Stack

- **Backend**: Flask 3.1, SQLAlchemy, SQLite (WAL mode, FTS5)
- **Frontend**: HTMX 1.9, custom CSS (no framework)
- **Security**: AES-GCM encryption at rest, HMAC request signing, RBAC
- **Deployment**: Docker Compose, Gunicorn

## Quick Start

```bash
docker compose up --build
```

Access: http://localhost:5000

`docker compose up --build` works from a clean checkout without a local `.env` file because
`docker-compose.yml` includes safe development defaults for `SECRET_KEY`, `HMAC_SECRET`,
`ENCRYPTION_KEY`, and `DATABASE_URL`. For custom values, copy `.env.example` to `.env`.
When bootstrap demo users are enabled, temporary credentials are printed once in the container logs
instead of using fixed defaults.

The bundled Compose stack is a local development/demo profile. For production-style deployment,
set `APP_CONFIG_NAME=production`, provide real secrets, and keep
`ALLOW_DEFAULT_BOOTSTRAP_USERS=0` so predictable bootstrap credentials are not created.

> **Production deployment**: copy `.env.example` to `.env`, generate strong keys, set
> `APP_CONFIG_NAME=production`, keep `ALLOW_DEFAULT_BOOTSTRAP_USERS=0`, and supply a real
> base64-encoded 32-byte `ENCRYPTION_KEY` before running.

### Hardened production compose profile

For a hardened deployment path, use the dedicated production compose file:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

That profile:

- requires explicit `SECRET_KEY`, `HMAC_SECRET`, and `ENCRYPTION_KEY`
- forces `APP_CONFIG_NAME=production`
- disables default bootstrap users with `ALLOW_DEFAULT_BOOTSTRAP_USERS=0`

## Local Development (without Docker)

```bash
pip install -r requirements.txt

export FLASK_APP=app
export FLASK_ENV=development
# Optional but required for encrypted fields and backups:
export ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())")

flask db-init   # creates tables and FTS5 index
flask db-seed   # loads default roles, permissions, org units, and admin/staff users
flask run       # starts development server on http://127.0.0.1:5000
```

## Features

- Property listing management with publish/review workflow (draft → pending_review → published)
- Training class registration and star-rating reviews with attendee verification
- Drug knowledge base with FTS5 full-text search and CSV bulk import
- Content moderation with appeals (14-day filing window, 5 business-day resolution)
- Multi-level RBAC: campus / college / department / section org hierarchy
- Temporary permission grants with automatic expiry
- Immutable audit logs (SQLAlchemy event listeners prevent modification)
- Offline-capable: service worker with stale-while-revalidate caching and queued writes
- AES-GCM field-level encryption for PII (email, full name, address)
- Encrypted backups with 30-day retention

## Running Tests

```bash
# In Docker
docker compose exec web bash run_tests.sh

# Locally
pip install -r requirements.txt
bash run_tests.sh
```

`run_tests.sh` always runs unit + API tests. E2E tests run only when Playwright and Chromium are installed; otherwise they are skipped without failing the suite.

## API Endpoints

### Authentication — `/auth`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login` | Login page |
| POST | `/auth/login` | Authenticate (JSON or form) |
| GET | `/auth/register` | Register page |
| POST | `/auth/register` | Create account |
| POST | `/auth/logout` | Sign out |
| GET | `/auth/me` | Current user info |
| POST | `/auth/change-password` | Change password |

### Listings — `/api/listings`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/listings` | List listings (paginated) |
| POST | `/api/listings` | Create listing |
| GET | `/api/listings/<id>` | Get listing detail |
| PUT | `/api/listings/<id>` | Update listing |
| POST | `/api/listings/<id>/status` | Change listing status |

### Reviews — `/api`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/classes/<id>/reviews` | List reviews for class |
| POST | `/api/classes/<id>/reviews` | Submit review (attendees only) |
| GET | `/api/reviews/<id>` | Get review |
| PUT | `/api/reviews/<id>` | Update review |
| POST | `/api/reviews/<id>/reply` | Add coach reply |
| PUT | `/api/replies/<id>` | Update coach reply |

### Moderation — `/api/moderation`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/moderation/reports` | Report a review |
| POST | `/api/moderation/reports/<id>/hide` | Hide review |
| POST | `/api/moderation/reports/<id>/restore` | Restore review |
| POST | `/api/moderation/reports/<id>/finalize` | Finalize report |
| POST | `/api/moderation/appeals` | File appeal |
| POST | `/api/moderation/appeals/<id>/resolve` | Resolve appeal |

### Drugs — `/api/drugs`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/drugs` | Search/list drugs |
| POST | `/api/drugs` | Create drug entry |
| GET | `/api/drugs/<id>` | Get drug detail |
| PUT | `/api/drugs/<id>` | Update drug |
| POST | `/api/drugs/<id>/submit` | Submit for approval |
| POST | `/api/drugs/<id>/approve` | Approve drug |
| POST | `/api/drugs/<id>/reject` | Reject drug |
| POST | `/api/drugs/import` | Bulk CSV import |

### Admin — `/api/admin`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/users` | List users |
| GET | `/api/admin/users/<id>` | Get user |
| POST | `/api/admin/users/<id>/roles` | Assign role |
| DELETE | `/api/admin/users/<id>/roles/<name>` | Remove role |
| POST | `/api/admin/users/<id>/temp-grants` | Grant temp permission |
| POST | `/api/admin/temp-grants/<id>/revoke` | Revoke grant |
| GET | `/api/admin/org-units` | List org units |
| POST | `/api/admin/org-units` | Create org unit |
| GET | `/api/admin/audit-logs` | View audit trail |
| POST | `/api/admin/backup` | Run backup |
| GET | `/api/admin/backups` | List backups |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session signing key | *(required in production)* |
| `HMAC_SECRET` | API request signing secret | *(required in production)* |
| `ENCRYPTION_KEY` | Base64-encoded 32-byte AES-GCM key | *(required — app refuses to encrypt/backup without it)* |
| `DATABASE_URL` | SQLite connection string | `sqlite:///dev.db` |
| `FLASK_ENV` | Environment: development/production | `development` |

Generate keys:
```bash
# SECRET_KEY and HMAC_SECRET
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

## Project Structure

```
clinical_ops_portal/
├── app/
│   ├── __init__.py              # App factory, CLI commands, FTS table setup
│   ├── config.py                # Dev / Test / Prod configuration
│   ├── extensions.py            # SQLAlchemy, LoginManager, CSRF
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── user.py              # User, Role, Permission, TempGrant
│   │   ├── organization.py      # OrgUnit, UserOrgUnit
│   │   ├── listing.py           # PropertyListing, ListingAmenity, StatusHistory
│   │   ├── training.py          # TrainingClass, ClassAttendee, ClassReview, CoachReply
│   │   ├── moderation.py        # ModerationReport, ModerationAppeal
│   │   ├── drug.py              # Drug, TagTaxonomy
│   │   ├── audit.py             # AuditLog (immutable)
│   │   └── queue.py             # JobQueue
│   ├── services/                # Business logic
│   │   ├── auth_service.py
│   │   ├── listing_service.py
│   │   ├── review_service.py
│   │   ├── moderation_service.py
│   │   ├── drug_service.py
│   │   ├── permission_service.py
│   │   ├── audit_service.py
│   │   ├── backup_service.py
│   │   └── queue_service.py
│   ├── api/                     # Flask Blueprints
│   │   ├── auth_routes.py
│   │   ├── listing_routes.py
│   │   ├── review_routes.py
│   │   ├── moderation_routes.py
│   │   ├── drug_routes.py
│   │   ├── admin_routes.py
│   │   ├── page_routes.py       # Server-rendered page routes
│   │   ├── listing_page_routes.py
│   │   ├── class_page_routes.py
│   │   ├── moderation_page_routes.py
│   │   └── drug_page_routes.py
│   ├── templates/               # Jinja2 + HTMX templates
│   ├── static/                  # CSS, JS, Service Worker
│   └── utils/                   # Validators, decorators, crypto, masking, constants
├── scripts/seed_data.py         # Seeds roles, permissions, org hierarchy, default users
├── unit_tests/                  # Service-layer unit tests (130 tests)
├── API_tests/                   # HTTP endpoint integration tests (42 tests)
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── run_tests.sh
```

## Disaster Recovery

| Metric | Value |
|--------|-------|
| RPO | 24 hours (nightly backups via `POST /api/admin/backup`) |
| RTO | ~4 hours (restore SQLite file and restart container) |
| Retention | 30 days (configurable via `BACKUP_RETENTION_DAYS`) |

**Restore procedure:**
1. Stop the container: `docker compose down`
2. Decrypt the backup: `openssl enc -d -aes-256-gcm` is **not** applicable — use a Python snippet:
   ```python
   import base64, os
   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
   key = base64.b64decode(os.environ['ENCRYPTION_KEY'])
   raw = open('backup_YYYYMMDD_HHMMSS.db.enc', 'rb').read()
   plain = AESGCM(key).decrypt(raw[:12], raw[12:], None)
   open('clinical_ops.db', 'wb').write(plain)
   ```
3. Copy the decrypted file into the volume: `cp clinical_ops.db <volume_path>/clinical_ops.db`
4. Restart: `docker compose up -d`

## Default Roles and Permissions

| Role | Permissions |
|------|------------|
| `org_admin` | All permissions |
| `property_manager` | listing.create, listing.edit, listing.publish, listing.delete, listing.lock |
| `instructor` | review.reply |
| `content_moderator` | review.moderate |
| `staff` | review.create, listing.create |

## Security Notes

- Passwords are hashed with Werkzeug's PBKDF2-SHA256 (min 8 chars, uppercase, digit, special char required)
- PII fields (email, full_name, address) are encrypted with AES-256-GCM using per-value random nonces
- Audit logs are write-once (SQLAlchemy `before_update` event raises `RuntimeError`)
- CSRF protection enabled on all state-changing form submissions (Flask-WTF)
- Session cookies: `HttpOnly`, `SameSite=Lax`, `Secure` in production
