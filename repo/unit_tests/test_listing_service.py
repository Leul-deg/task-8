import pytest
from datetime import date, timedelta
from app import create_app
from app.extensions import db as _db
from app.models.user import User, Role
from app.models.organization import OrgUnit
from app.services.listing_service import (
    create_listing, update_listing, change_listing_status,
    expire_stale_listings, get_listing_detail, get_listings,
)
from app.utils.constants import OrgUnitLevel, ListingStatus


@pytest.fixture(scope='function')
def app():
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


def _setup(db):
    u = User(username='pm', email='pm@test.com')
    u.set_password('Secret1!')
    org = OrgUnit(name='Test Org', code='TO1', level=OrgUnitLevel.CAMPUS.value)
    _db.session.add_all([u, org])
    _db.session.commit()
    return u, org


def _listing_data(org_unit_id):
    return {
        'title': 'Nice Apartment',
        'address_line1': '42 Baker St',
        'city': 'Springfield',
        'state': 'IL',
        'zip_code': '62701',
        'monthly_rent_cents': 120000,
        'deposit_cents': 240000,
        'lease_start': date(2026, 6, 1),
        'lease_end': date(2027, 5, 31),
        'org_unit_id': org_unit_id,
        'amenities': ['parking', 'wifi'],
    }


def _make_admin_user(suffix='adm'):
    admin_role = Role.query.filter_by(name='org_admin').first()
    if not admin_role:
        admin_role = Role(name='org_admin', is_system=True)
        _db.session.add(admin_role)
        _db.session.flush()
    u = User(username=f'admin_{suffix}', email=f'admin_{suffix}@test.com')
    u.set_password('Secret1!')
    _db.session.add(u)
    _db.session.flush()
    u.roles.append(admin_role)
    _db.session.commit()
    return u


# ---------------------------------------------------------------------------
# Existing tests — updated to respect the new transition rules
# ---------------------------------------------------------------------------

class TestCreateListing:
    def test_creates_with_draft_status(self, db):
        u, org = _setup(db)
        listing = create_listing(_listing_data(org.id), u)
        assert listing.id is not None
        assert listing.status == ListingStatus.DRAFT.value

    def test_stores_rent_in_cents(self, db):
        u, org = _setup(db)
        listing = create_listing(_listing_data(org.id), u)
        assert listing.monthly_rent_cents == 120000

    def test_amenities_created(self, db):
        u, org = _setup(db)
        listing = create_listing(_listing_data(org.id), u)
        amenity_names = [a.name for a in listing.amenities]
        assert 'parking' in amenity_names
        assert 'wifi' in amenity_names


class TestChangeListingStatus:
    def test_publish_sets_published_at(self, db):
        """draft → pending_review → published (correct workflow)."""
        u, org = _setup(db)
        listing = create_listing(_listing_data(org.id), u)
        change_listing_status(listing, ListingStatus.PENDING_REVIEW.value, u)
        listing = change_listing_status(listing, ListingStatus.PUBLISHED.value, u)
        assert listing.published_at is not None
        assert listing.status == ListingStatus.PUBLISHED.value

    def test_status_history_recorded(self, db):
        u, org = _setup(db)
        listing = create_listing(_listing_data(org.id), u)
        change_listing_status(listing, ListingStatus.PENDING_REVIEW.value, u, 'Ready for review')
        history = listing.status_history
        assert any(h.new_status == ListingStatus.PENDING_REVIEW.value for h in history)


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------

class TestListingValidation:
    def test_create_invalid_zip(self, app):
        with app.app_context():
            u, org = _setup(_db)
            data = {**_listing_data(org.id), 'zip_code': 'abc'}
            with pytest.raises(ValueError, match="zip code"):
                create_listing(data, u)

    def test_create_negative_rent(self, app):
        with app.app_context():
            u, org = _setup(_db)
            data = {**_listing_data(org.id), 'monthly_rent_cents': -100}
            with pytest.raises(ValueError, match="rent must be positive"):
                create_listing(data, u)

    def test_create_zero_rent(self, app):
        with app.app_context():
            u, org = _setup(_db)
            data = {**_listing_data(org.id), 'monthly_rent_cents': 0}
            with pytest.raises(ValueError, match="rent must be positive"):
                create_listing(data, u)

    def test_create_negative_deposit(self, app):
        with app.app_context():
            u, org = _setup(_db)
            data = {**_listing_data(org.id), 'deposit_cents': -500}
            with pytest.raises(ValueError, match="Deposit cannot be negative"):
                create_listing(data, u)

    def test_create_invalid_lease_dates(self, app):
        with app.app_context():
            u, org = _setup(_db)
            data = {
                **_listing_data(org.id),
                'lease_start': date(2026, 12, 1),
                'lease_end': date(2026, 1, 1),
            }
            with pytest.raises(ValueError, match="end date must be after"):
                create_listing(data, u)

    def test_create_title_too_short(self, app):
        with app.app_context():
            u, org = _setup(_db)
            data = {**_listing_data(org.id), 'title': 'AB'}
            with pytest.raises(ValueError, match="3-200 characters"):
                create_listing(data, u)

    def test_create_title_too_long(self, app):
        with app.app_context():
            u, org = _setup(_db)
            data = {**_listing_data(org.id), 'title': 'A' * 201}
            with pytest.raises(ValueError, match="3-200 characters"):
                create_listing(data, u)

    def test_create_zero_deposit_allowed(self, app):
        """Zero deposit is valid (free deposit)."""
        with app.app_context():
            u, org = _setup(_db)
            data = {**_listing_data(org.id), 'deposit_cents': 0}
            listing = create_listing(data, u)
            assert listing.deposit_cents == 0


class TestStatusTransitions:
    def test_draft_to_pending_review(self, app):
        with app.app_context():
            u, org = _setup(_db)
            listing = create_listing(_listing_data(org.id), u)
            listing = change_listing_status(listing, ListingStatus.PENDING_REVIEW.value, u)
            assert listing.status == ListingStatus.PENDING_REVIEW.value

    def test_draft_to_published_fails(self, app):
        """draft → published is not allowed; must go through pending_review."""
        with app.app_context():
            u, org = _setup(_db)
            listing = create_listing(_listing_data(org.id), u)
            with pytest.raises(ValueError, match="Cannot transition"):
                change_listing_status(listing, ListingStatus.PUBLISHED.value, u)

    def test_published_to_expired_auto(self, app):
        """expire_stale_listings() marks published listings with past lease_end as expired."""
        with app.app_context():
            u, org = _setup(_db)
            data = {
                **_listing_data(org.id),
                'lease_start': date(2024, 1, 1),
                'lease_end': date(2024, 6, 30),  # already past
            }
            listing = create_listing(data, u)
            # Force status to published without going through workflow
            listing.status = ListingStatus.PUBLISHED.value
            _db.session.commit()

            count = expire_stale_listings()
            assert count == 1
            _db.session.refresh(listing)
            assert listing.status == ListingStatus.EXPIRED.value

    def test_locked_to_draft_requires_admin(self, app):
        """A non-admin user cannot unlock a listing."""
        with app.app_context():
            u, org = _setup(_db)
            listing = create_listing(_listing_data(org.id), u)
            # Force status to locked directly
            listing.status = ListingStatus.LOCKED.value
            _db.session.commit()

            with pytest.raises(PermissionError, match="org admins"):
                change_listing_status(listing, ListingStatus.DRAFT.value, u)

    def test_locked_to_draft_allowed_for_admin(self, app):
        """An org_admin CAN unlock a listing."""
        with app.app_context():
            _, org = _setup(_db)
            admin = _make_admin_user('unlock')
            data = _listing_data(org.id)
            listing = create_listing(data, admin)
            listing.status = ListingStatus.LOCKED.value
            _db.session.commit()

            listing = change_listing_status(listing, ListingStatus.DRAFT.value, admin)
            assert listing.status == ListingStatus.DRAFT.value

    def test_unpublish_requires_reason(self, app):
        """Unpublishing without a reason raises ValueError."""
        with app.app_context():
            u, org = _setup(_db)
            listing = create_listing(_listing_data(org.id), u)
            listing.status = ListingStatus.PUBLISHED.value
            _db.session.commit()

            with pytest.raises(ValueError, match="reason is required"):
                change_listing_status(listing, ListingStatus.UNPUBLISHED.value, u, reason=None)

    def test_unpublish_with_reason_succeeds(self, app):
        with app.app_context():
            u, org = _setup(_db)
            listing = create_listing(_listing_data(org.id), u)
            listing.status = ListingStatus.PUBLISHED.value
            _db.session.commit()

            listing = change_listing_status(
                listing, ListingStatus.UNPUBLISHED.value, u, reason='Taken offline for repairs'
            )
            assert listing.status == ListingStatus.UNPUBLISHED.value

    def test_invalid_transition_raises(self, app):
        with app.app_context():
            u, org = _setup(_db)
            listing = create_listing(_listing_data(org.id), u)
            # draft → expired is not in ALLOWED_TRANSITIONS
            with pytest.raises(ValueError, match="Cannot transition"):
                change_listing_status(listing, ListingStatus.EXPIRED.value, u)


class TestGetListings:
    def test_pagination(self, app):
        with app.app_context():
            u, org = _setup(_db)
            for i in range(5):
                data = {**_listing_data(org.id), 'title': f'Apt {i + 1}'}
                create_listing(data, u)
            result = get_listings(per_page=2, page=1)
            assert len(result['items']) == 2
            assert result['total'] == 5
            assert result['pages'] == 3

    def test_filter_by_rent_range(self, app):
        with app.app_context():
            u, org = _setup(_db)
            cheap = {**_listing_data(org.id), 'title': 'Cheap', 'monthly_rent_cents': 50000}
            expensive = {**_listing_data(org.id), 'title': 'Expensive', 'monthly_rent_cents': 300000}
            create_listing(cheap, u)
            create_listing(expensive, u)
            result = get_listings(min_rent=60000, max_rent=200000)
            assert result['total'] == 0
            result2 = get_listings(max_rent=60000)
            assert result2['total'] == 1
            assert result2['items'][0].title == 'Cheap'

    def test_search_by_title(self, app):
        with app.app_context():
            u, org = _setup(_db)
            create_listing({**_listing_data(org.id), 'title': 'Sunny Studio'}, u)
            create_listing({**_listing_data(org.id), 'title': 'Dark Basement'}, u)
            result = get_listings(search='sunny')
            assert result['total'] == 1
            assert result['items'][0].title == 'Sunny Studio'


class TestGetListingDetail:
    def test_includes_display_prices(self, app):
        with app.app_context():
            u, org = _setup(_db)
            listing = create_listing(_listing_data(org.id), u)
            detail = get_listing_detail(listing.id)
            assert detail['monthly_rent_display'] == '$1,200.00'
            assert detail['deposit_display'] == '$2,400.00'

    def test_includes_status_history(self, app):
        with app.app_context():
            u, org = _setup(_db)
            listing = create_listing(_listing_data(org.id), u)
            detail = get_listing_detail(listing.id)
            assert len(detail['status_history']) >= 1
            assert detail['status_history'][-1]['new_status'] == ListingStatus.DRAFT.value
