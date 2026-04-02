"""
E2E test fixtures.

Starts a real Flask server on a random port backed by a file-based SQLite
database so the service worker, IndexedDB, and HTMX partials all work inside
a real Chromium browser driven by pytest-playwright.
"""
import os
import threading
import pytest
from datetime import date
from werkzeug.serving import make_server
from app import create_app
from app.extensions import db as _db

_DB_PATH = f'/tmp/clinical_e2e_{os.getpid()}.db'


# ── Application & live server ─────────────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    application = create_app('testing')
    application.config.update({
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{_DB_PATH}',
        'WTF_CSRF_ENABLED': False,
        'LOGIN_MAX_ATTEMPTS_PER_IP': 0,
        'LOGIN_MAX_ATTEMPTS_PER_USERNAME': 0,
    })
    with application.app_context():
        _db.create_all()
        _seed()
        yield application
        _db.session.remove()
        _db.drop_all()
    try:
        os.unlink(_DB_PATH)
    except OSError:
        pass


@pytest.fixture(scope='session')
def flask_url(app):
    """Start a Werkzeug WSGI server on a random port in a daemon thread.

    Named ``flask_url`` (not ``live_server``) to avoid clashing with the
    ``live_server`` fixture that pytest-flask injects automatically.
    """
    server = make_server('127.0.0.1', 0, app)
    url = f'http://127.0.0.1:{server.server_port}'
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield url
    server.shutdown()


# ── Seed-data accessors ───────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def seeded_listing_id(app):
    with app.app_context():
        from app.models.listing import PropertyListing
        return PropertyListing.query.filter_by(title='E2E Test Listing').first().id


@pytest.fixture(scope='session')
def seeded_report_id(app):
    with app.app_context():
        from app.models.moderation import ModerationReport
        return ModerationReport.query.first().id


@pytest.fixture(scope='session')
def seeded_reply_class(app):
    """Returns (class_id, review_id) for the clean class used by reply tests."""
    with app.app_context():
        from app.models.training import TrainingClass, ClassReview
        tc = TrainingClass.query.filter_by(title='E2E Reply Class').first()
        review = ClassReview.query.filter_by(class_id=tc.id).first()
        return tc.id, review.id


# ── Seed function ─────────────────────────────────────────────────────────────

def _seed():
    from app.models.user import User, Role, Permission
    from app.models.organization import OrgUnit, UserOrgUnit
    from app.models.listing import PropertyListing
    from app.models.training import TrainingClass, ClassAttendee
    from app.utils.constants import OrgUnitLevel, DEFAULT_PERMISSIONS, DEFAULT_ROLES
    from app.services.review_service import create_review

    # Permissions
    perms = {}
    for pdata in DEFAULT_PERMISSIONS:
        p = Permission(**pdata)
        _db.session.add(p)
        perms[pdata['codename']] = p
    _db.session.flush()

    # Roles
    roles = {}
    for rdata in DEFAULT_ROLES:
        r = Role(**rdata)
        _db.session.add(r)
        roles[rdata['name']] = r
    _db.session.flush()

    # org_admin gets all permissions
    for p in perms.values():
        roles['org_admin'].permissions.append(p)

    # Org unit
    org = OrgUnit(name='E2E Campus', code='E2E1', level=OrgUnitLevel.CAMPUS.value)
    _db.session.add(org)
    _db.session.flush()

    # Admin user
    admin = User(username='admin', email='admin@e2e.test', full_name='Admin User')
    admin.set_password('admin123')
    _db.session.add(admin)
    _db.session.flush()
    admin.roles.append(roles['org_admin'])
    _db.session.add(UserOrgUnit(user_id=admin.id, org_unit_id=org.id, is_primary=True))

    # Instructor role permissions
    for codename in ['class.create', 'review.reply']:
        roles['instructor'].permissions.append(perms[codename])

    # Staff user (can create reviews)
    for codename in ['review.create', 'listing.create']:
        roles['staff'].permissions.append(perms[codename])
    staff = User(username='staffuser', email='staff@e2e.test', full_name='Staff Member')
    staff.set_password('staffpass')
    _db.session.add(staff)
    _db.session.flush()
    staff.roles.append(roles['staff'])
    _db.session.add(UserOrgUnit(user_id=staff.id, org_unit_id=org.id, is_primary=True))

    # Draft listing — used by listing-edit E2E tests
    listing = PropertyListing(
        title='E2E Test Listing',
        address_line1='1 Test Street',
        city='Springfield',
        state='IL',
        zip_code='62701',
        monthly_rent_cents=100000,
        deposit_cents=50000,
        lease_start=date(2026, 7, 1),
        lease_end=date(2027, 6, 30),
        org_unit_id=org.id,
        created_by_id=admin.id,
        status='draft',
    )
    _db.session.add(listing)

    # Training class + attended staff member — used by moderation E2E tests
    tc = TrainingClass(
        title='E2E Test Class',
        instructor_id=admin.id,
        org_unit_id=org.id,
        class_date=date(2026, 8, 1),
        location='Room 1',
        max_attendees=30,
    )
    _db.session.add(tc)
    _db.session.flush()
    _db.session.add(ClassAttendee(class_id=tc.id, user_id=staff.id, attended=True))
    _db.session.commit()

    # Review with flagged keyword → auto_flag_review creates a ModerationReport
    create_review(tc.id, staff, {
        'rating': 2,
        'comment': 'The instructor was stupid and the class was not helpful at all.',
    })
    _db.session.commit()

    # Second class with a clean review — used by coach-reply E2E tests.
    # Separate from the flagged-review class so moderation tests don't
    # hide this review and break reply-form assertions.
    tc2 = TrainingClass(
        title='E2E Reply Class',
        instructor_id=admin.id,
        org_unit_id=org.id,
        class_date=date(2026, 9, 1),
        location='Room 2',
        max_attendees=30,
    )
    _db.session.add(tc2)
    _db.session.flush()
    _db.session.add(ClassAttendee(class_id=tc2.id, user_id=staff.id, attended=True))
    _db.session.commit()

    create_review(tc2.id, staff, {
        'rating': 4,
        'comment': 'Very clear explanations and well-organized material throughout.',
    })
    _db.session.commit()
