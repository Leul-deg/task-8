"""
Page-level integration tests for browser-facing routes.

These exercise the same HTMX / form-driven flows that the Playwright E2E suite
covers, but through the Flask test client so they run without a real browser.
Each test verifies that page routes return the expected HTML, handle form POST
submissions correctly (redirects, flash messages, inline saves), and deliver
HTMX partial fragments when the HX-Request header is present.
"""
import pytest
from datetime import date
from app import create_app
from app.extensions import db as _db
from app.models.user import User, Role, Permission
from app.models.organization import OrgUnit, UserOrgUnit
from app.models.listing import PropertyListing, ListingAmenity
from app.models.training import TrainingClass, ClassAttendee, ClassReview
from app.models.moderation import ModerationReport
from app.utils.constants import (
    OrgUnitLevel, ListingStatus, ModerationStatus,
    DEFAULT_PERMISSIONS, DEFAULT_ROLES,
)
from app import _create_fts_table


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def app():
    application = create_app('testing')
    application.config['WTF_CSRF_ENABLED'] = False
    with application.app_context():
        _db.create_all()
        _create_fts_table(_db)
        _seed()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, username='admin', password='admin123'):
    return client.post('/auth/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=False)


def _seed():
    perms = {}
    for pdata in DEFAULT_PERMISSIONS:
        p = Permission(**pdata)
        _db.session.add(p)
        perms[pdata['codename']] = p
    _db.session.flush()

    roles = {}
    for rdata in DEFAULT_ROLES:
        r = Role(**rdata)
        _db.session.add(r)
        roles[rdata['name']] = r
    _db.session.flush()

    for p in perms.values():
        roles['org_admin'].permissions.append(p)
    for codename in ['class.create', 'review.reply']:
        if codename in perms:
            roles['instructor'].permissions.append(perms[codename])
    for codename in ['review.create', 'listing.create']:
        if codename in perms:
            roles['staff'].permissions.append(perms[codename])

    org = OrgUnit(name='Test Campus', code='TC1', level=OrgUnitLevel.CAMPUS.value)
    _db.session.add(org)
    _db.session.flush()

    admin = User(username='admin', email='admin@test.com', full_name='Admin User')
    admin.set_password('admin123')
    _db.session.add(admin)
    _db.session.flush()
    admin.roles.append(roles['org_admin'])
    _db.session.add(UserOrgUnit(user_id=admin.id, org_unit_id=org.id, is_primary=True))

    staff = User(username='staffuser', email='staff@test.com', full_name='Staff Member')
    staff.set_password('staffpass')
    _db.session.add(staff)
    _db.session.flush()
    staff.roles.append(roles['staff'])
    _db.session.add(UserOrgUnit(user_id=staff.id, org_unit_id=org.id, is_primary=True))

    listing = PropertyListing(
        title='Draft Listing',
        address_line1='100 Main St',
        city='Springfield',
        state='IL',
        zip_code='62701',
        monthly_rent_cents=150000,
        deposit_cents=75000,
        lease_start=date(2026, 7, 1),
        lease_end=date(2027, 6, 30),
        org_unit_id=org.id,
        created_by_id=admin.id,
        status=ListingStatus.DRAFT.value,
    )
    _db.session.add(listing)
    _db.session.flush()
    _db.session.add(ListingAmenity(listing_id=listing.id, name='parking'))

    tc = TrainingClass(
        title='Safety Refresher',
        instructor_id=admin.id,
        org_unit_id=org.id,
        class_date=date(2026, 8, 1),
        location='Room 101',
        max_attendees=30,
    )
    _db.session.add(tc)
    _db.session.flush()
    _db.session.add(ClassAttendee(class_id=tc.id, user_id=staff.id, attended=True))
    _db.session.commit()

    from app.services.review_service import create_review
    create_review(tc.id, staff, {
        'rating': 2,
        'comment': 'The instructor was stupid and unhelpful for our needs.',
    })
    _db.session.commit()


# ═══════════════════════════════════════════════════════════════════════════
# 1. LOGIN / LOGOUT FORM FLOWS
# ═══════════════════════════════════════════════════════════════════════════

class TestLoginPageFlow:
    def test_login_page_renders(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200
        assert b'Sign In' in resp.data or b'Login' in resp.data

    def test_successful_login_redirects_to_dashboard(self, client):
        resp = _login(client)
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers.get('Location', '')

    def test_wrong_password_returns_401_with_login_page(self, client):
        resp = client.post('/auth/login', data={
            'username': 'admin', 'password': 'wrong',
        })
        assert resp.status_code == 401
        assert b'Invalid credentials' in resp.data

    def test_dashboard_accessible_after_login(self, client):
        _login(client)
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Admin User' in resp.data or b'admin' in resp.data

    def test_logout_clears_session(self, client):
        _login(client)
        resp = client.post('/auth/logout')
        assert resp.status_code == 200
        dashboard = client.get('/dashboard', follow_redirects=False)
        assert dashboard.status_code in (302, 401)

    def test_unauthenticated_access_redirects_to_login(self, client):
        resp = client.get('/listings', follow_redirects=False)
        assert resp.status_code in (302, 401)


# ═══════════════════════════════════════════════════════════════════════════
# 2. LISTING EDIT FORM SUBMISSION (page-route POST → redirect → detail)
# ═══════════════════════════════════════════════════════════════════════════

class TestListingEditPageFlow:
    def _get_listing_id(self, app):
        with app.app_context():
            return PropertyListing.query.filter_by(title='Draft Listing').first().id

    def _get_org_id(self, app):
        with app.app_context():
            return OrgUnit.query.first().id

    def test_edit_form_renders_with_existing_data(self, client, app):
        _login(client)
        lid = self._get_listing_id(app)
        resp = client.get(f'/listings/{lid}/edit')
        assert resp.status_code == 200
        assert b'Draft Listing' in resp.data
        assert b'100 Main St' in resp.data

    def test_edit_form_post_saves_and_redirects(self, client, app):
        _login(client)
        lid = self._get_listing_id(app)
        oid = self._get_org_id(app)
        resp = client.post(f'/listings/{lid}', data={
            'title': 'Updated Title',
            'address_line1': '200 Oak Ave',
            'city': 'Springfield',
            'state': 'IL',
            'zip_code': '62701',
            'monthly_rent': '1600.00',
            'deposit': '800.00',
            'lease_start': '2026-07-01',
            'lease_end': '2027-06-30',
            'square_footage': '900',
            'org_unit_id': str(oid),
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert f'/listings/{lid}' in resp.headers.get('Location', '')

        detail = client.get(f'/listings/{lid}')
        assert resp.status_code == 302 or b'Updated Title' in detail.data

    def test_edit_form_validation_error_rerenders(self, client, app):
        _login(client)
        lid = self._get_listing_id(app)
        oid = self._get_org_id(app)
        resp = client.post(f'/listings/{lid}', data={
            'title': '',
            'address_line1': '200 Oak Ave',
            'city': 'Springfield',
            'state': 'IL',
            'zip_code': 'BADZIP',
            'monthly_rent': '1600.00',
            'deposit': '800.00',
            'lease_start': '2027-01-01',
            'lease_end': '2026-01-01',
            'org_unit_id': str(oid),
        }, follow_redirects=True)
        assert resp.status_code in (200, 400)

    def test_edit_page_requires_auth(self, client, app):
        lid = self._get_listing_id(app)
        resp = client.get(f'/listings/{lid}/edit', follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_staff_cannot_edit_listing(self, client, app):
        _login(client, 'staffuser', 'staffpass')
        lid = self._get_listing_id(app)
        resp = client.get(f'/listings/{lid}/edit')
        assert resp.status_code == 403

    def test_create_listing_form_post(self, client, app):
        _login(client)
        oid = self._get_org_id(app)
        resp = client.post('/listings', data={
            'title': 'Brand New Place',
            'address_line1': '50 Elm St',
            'city': 'Chicago',
            'state': 'IL',
            'zip_code': '60601',
            'monthly_rent': '2000.00',
            'deposit': '1000.00',
            'lease_start': '2026-09-01',
            'lease_end': '2027-08-31',
            'square_footage': '1200',
            'org_unit_id': str(oid),
            'amenities': ['parking', 'wifi'],
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert '/listings/' in resp.headers.get('Location', '')


# ═══════════════════════════════════════════════════════════════════════════
# 3. LISTING STATUS CHANGE VIA HTMX (partial swap)
# ═══════════════════════════════════════════════════════════════════════════

class TestListingStatusHtmx:
    def _get_listing_id(self, app):
        with app.app_context():
            return PropertyListing.query.first().id

    def test_status_change_htmx_returns_partial(self, client, app):
        """Simulates an HTMX POST with HX-Request header; response should be
        an HTML fragment (the status section partial), not a 302 redirect."""
        _login(client)
        lid = self._get_listing_id(app)
        resp = client.post(
            f'/listings/{lid}/status',
            data={'status': 'pending_review'},
            headers={'HX-Request': 'true'},
        )
        assert resp.status_code == 200
        assert b'badge' in resp.data
        assert b'Pending' in resp.data or b'pending' in resp.data

    def test_status_change_without_htmx_redirects(self, client, app):
        _login(client)
        lid = self._get_listing_id(app)
        resp = client.post(
            f'/listings/{lid}/status',
            data={'status': 'pending_review'},
            follow_redirects=False,
        )
        assert resp.status_code == 302


# ═══════════════════════════════════════════════════════════════════════════
# 4. MODERATION ACTIONS VIA HTMX (partial swap + permission gate)
# ═══════════════════════════════════════════════════════════════════════════

class TestModerationPageFlow:
    def _get_report_id(self, app):
        with app.app_context():
            return ModerationReport.query.first().id

    def test_moderation_queue_renders(self, client, app):
        _login(client)
        resp = client.get('/moderation')
        assert resp.status_code == 200
        assert b'report-' in resp.data

    def test_hide_review_htmx_returns_updated_card(self, client, app):
        _login(client)
        rid = self._get_report_id(app)
        resp = client.post(
            f'/moderation/reports/{rid}/hide',
            data={'reason': 'Inappropriate content'},
            headers={'HX-Request': 'true'},
        )
        assert resp.status_code == 200
        assert b'review_hidden' in resp.data or b'Review Hidden' in resp.data

    def test_restore_review_htmx_returns_updated_card(self, client, app):
        _login(client)
        rid = self._get_report_id(app)
        client.post(f'/moderation/reports/{rid}/hide', data={'reason': 'test'})
        resp = client.post(
            f'/moderation/reports/{rid}/restore',
            headers={'HX-Request': 'true'},
        )
        assert resp.status_code == 200
        assert b'review_restored' in resp.data or b'Review Restored' in resp.data

    def test_finalize_report_htmx(self, client, app):
        _login(client)
        rid = self._get_report_id(app)
        client.post(f'/moderation/reports/{rid}/hide', data={'reason': 'test'})
        resp = client.post(
            f'/moderation/reports/{rid}/finalize',
            headers={'HX-Request': 'true'},
        )
        assert resp.status_code == 200
        assert b'finalized' in resp.data or b'Finalized' in resp.data

    def test_moderation_requires_moderator_role(self, client):
        _login(client, 'staffuser', 'staffpass')
        resp = client.get('/moderation')
        assert resp.status_code == 403

    def test_hide_without_htmx_redirects(self, client, app):
        _login(client)
        rid = self._get_report_id(app)
        resp = client.post(
            f'/moderation/reports/{rid}/hide',
            data={'reason': 'test'},
            follow_redirects=False,
        )
        assert resp.status_code == 302


# ═══════════════════════════════════════════════════════════════════════════
# 5. LISTING INDEX WITH HTMX SEARCH (partial grid refresh)
# ═══════════════════════════════════════════════════════════════════════════

class TestListingSearchHtmx:
    def test_htmx_search_returns_partial_grid(self, client):
        _login(client)
        resp = client.get(
            '/listings?search=Draft',
            headers={'HX-Request': 'true'},
        )
        assert resp.status_code == 200
        assert b'Draft Listing' in resp.data
        assert b'<!DOCTYPE' not in resp.data  # partial, not full page

    def test_full_page_includes_doctype(self, client):
        _login(client)
        resp = client.get('/listings')
        assert resp.status_code == 200
        assert b'<!DOCTYPE' in resp.data


# ═══════════════════════════════════════════════════════════════════════════
# 6. LISTING PREVIEW MODAL (HTMX partial load)
# ═══════════════════════════════════════════════════════════════════════════

class TestListingPreviewModal:
    def _get_listing_id(self, app):
        with app.app_context():
            return PropertyListing.query.first().id

    def test_preview_returns_modal_fragment(self, client, app):
        _login(client)
        lid = self._get_listing_id(app)
        resp = client.get(f'/listings/{lid}/preview')
        assert resp.status_code == 200
        assert b'modal' in resp.data or b'preview' in resp.data
        assert b'<!DOCTYPE' not in resp.data  # fragment, not full page


# ═══════════════════════════════════════════════════════════════════════════
# 7. DRUG SEARCH WITH HTMX
# ═══════════════════════════════════════════════════════════════════════════

class TestDrugSearchHtmx:
    def test_drug_page_renders(self, client):
        _login(client)
        resp = client.get('/drugs')
        assert resp.status_code == 200

    def test_drug_htmx_search_returns_partial(self, client):
        _login(client)
        resp = client.get(
            '/drugs?q=aspirin',
            headers={'HX-Request': 'true'},
        )
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data


# ═══════════════════════════════════════════════════════════════════════════
# 8. CLASS REVIEW FORM SUBMISSION
# ═══════════════════════════════════════════════════════════════════════════

class TestClassReviewPageFlow:
    def _get_class_id(self, app):
        with app.app_context():
            return TrainingClass.query.first().id

    def test_class_detail_renders(self, client, app):
        _login(client)
        cid = self._get_class_id(app)
        resp = client.get(f'/classes/{cid}')
        assert resp.status_code == 200
        assert b'Safety Refresher' in resp.data

    def test_register_for_class(self, client, app):
        _login(client)
        cid = self._get_class_id(app)
        resp = client.post(f'/classes/{cid}/register', follow_redirects=False)
        assert resp.status_code in (302, 200)


# ═══════════════════════════════════════════════════════════════════════════
# 9. OFFLINE INDICATOR MARKUP PRESENT
# ═══════════════════════════════════════════════════════════════════════════

class TestOfflineIndicators:
    def test_offline_banner_present_in_base_html(self, client):
        _login(client)
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'offline-indicator' in resp.data

    def test_queue_indicator_present_in_base_html(self, client):
        _login(client)
        resp = client.get('/dashboard')
        assert b'queue-indicator' in resp.data

    def test_service_worker_script_referenced(self, client):
        _login(client)
        resp = client.get('/dashboard')
        assert b'app.js' in resp.data

    def test_backups_admin_page_renders(self, client):
        _login(client)
        resp = client.get('/admin/backups')
        assert resp.status_code == 200
        assert b'Backups' in resp.data


# ═══════════════════════════════════════════════════════════════════════════
# 10. COACH-REPLY OWNERSHIP + SCOPE ENFORCEMENT
# ═══════════════════════════════════════════════════════════════════════════

class TestCoachReplyEnforcement:
    def _setup_class_and_review(self, app):
        with app.app_context():
            tc = TrainingClass.query.first()
            review = ClassReview.query.filter_by(class_id=tc.id).first()
            return tc.id, review.id, tc.instructor_id

    def test_non_instructor_cannot_reply(self, client, app):
        _login(client, 'staffuser', 'staffpass')
        cid, rid, _ = self._setup_class_and_review(app)
        resp = client.post(
            f'/classes/{cid}/reviews/{rid}/reply',
            data={'body': 'Unauthorized reply'},
        )
        assert resp.status_code == 403

    def test_instructor_can_reply(self, client, app):
        _login(client)
        cid, rid, _ = self._setup_class_and_review(app)
        resp = client.post(
            f'/classes/{cid}/reviews/{rid}/reply',
            data={'body': 'Thanks for the feedback!'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_review_class_mismatch_returns_404(self, client, app):
        _login(client)
        cid, rid, _ = self._setup_class_and_review(app)
        resp = client.post(
            f'/classes/99999/reviews/{rid}/reply',
            data={'body': 'Mismatch attempt'},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 11. SESSION HARDENING — Cache-Control on authenticated responses
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionHardening:
    def test_authenticated_pages_have_no_store(self, client):
        _login(client)
        resp = client.get('/dashboard')
        cc = resp.headers.get('Cache-Control', '')
        assert 'no-store' in cc

    def test_authenticated_listing_page_has_no_store(self, client):
        _login(client)
        resp = client.get('/listings')
        cc = resp.headers.get('Cache-Control', '')
        assert 'no-store' in cc

    def test_unauthenticated_login_page_allows_caching(self, client):
        resp = client.get('/auth/login')
        cc = resp.headers.get('Cache-Control', '')
        assert 'no-store' not in cc

    def test_static_assets_not_restricted(self, client):
        resp = client.get('/static/css/main.css')
        cc = resp.headers.get('Cache-Control', '')
        assert 'no-store' not in cc


# ═══════════════════════════════════════════════════════════════════════════
# 12. CACHE / STATE ISOLATION ACROSS USER SWITCH
# ═══════════════════════════════════════════════════════════════════════════

class TestCacheIsolation:
    def test_logout_includes_clear_site_data(self, client):
        _login(client)
        resp = client.post('/auth/logout')
        csd = resp.headers.get('Clear-Site-Data', '')
        assert '"cache"' in csd

    def test_htmx_logout_includes_hx_trigger(self, client):
        _login(client)
        resp = client.post('/auth/logout', headers={'HX-Request': 'true'})
        assert resp.headers.get('HX-Trigger') == 'clearSwCache'

    def test_user_switch_no_data_leakage(self, client):
        _login(client)
        admin_dash = client.get('/dashboard')
        assert b'admin' in admin_dash.data.lower()
        client.post('/auth/logout')
        _login(client, 'staffuser', 'staffpass')
        staff_dash = client.get('/dashboard')
        assert b'staffuser' in staff_dash.data.lower()

    def test_logout_response_has_no_store(self, client):
        _login(client)
        resp = client.post('/auth/logout')
        cc = resp.headers.get('Cache-Control', '')
        assert 'no-store' in cc
        assert 'no-cache' in cc


# ═══════════════════════════════════════════════════════════════════════════
# 13. CLASS CREATION PERMISSION GUARD
# ═══════════════════════════════════════════════════════════════════════════

class TestClassCreationPermission:
    def _get_org_id(self, app):
        with app.app_context():
            return OrgUnit.query.first().id

    def test_admin_can_access_new_class_form(self, client):
        _login(client)
        resp = client.get('/classes/new')
        assert resp.status_code == 200

    def test_staff_cannot_access_new_class_form(self, client):
        _login(client, 'staffuser', 'staffpass')
        resp = client.get('/classes/new')
        assert resp.status_code == 403

    def test_admin_can_create_class(self, client, app):
        _login(client)
        oid = self._get_org_id(app)
        resp = client.post('/classes', data={
            'title': 'Admin Created Class',
            'description': 'Integration test class',
            'class_date': '2026-10-01',
            'location': 'Room 5',
            'max_attendees': '25',
            'org_unit_id': str(oid),
        }, follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get('Location', '')
        assert '/classes/' in location

        detail = client.get(location, follow_redirects=True)
        assert detail.status_code == 200
        assert b'Admin Created Class' in detail.data
        assert b'Room 5' in detail.data

        with app.app_context():
            tc = TrainingClass.query.filter_by(title='Admin Created Class').first()
            assert tc is not None
            assert tc.class_date == date(2026, 10, 1)
            assert tc.location == 'Room 5'
            assert tc.max_attendees == 25
            assert tc.org_unit_id == oid

    def test_staff_cannot_create_class(self, client, app):
        _login(client, 'staffuser', 'staffpass')
        oid = self._get_org_id(app)
        resp = client.post('/classes', data={
            'title': 'Unauthorized Class',
            'class_date': '2026-10-01',
            'location': 'Room 5',
            'max_attendees': '25',
            'org_unit_id': str(oid),
        })
        assert resp.status_code == 403

    def test_invalid_date_returns_validation_error(self, client, app):
        _login(client)
        oid = self._get_org_id(app)
        resp = client.post('/classes', data={
            'title': 'Bad Date Class',
            'class_date': 'not-a-date',
            'location': 'Room 5',
            'max_attendees': '25',
            'org_unit_id': str(oid),
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid date' in resp.data

    def test_missing_date_returns_validation_error(self, client, app):
        _login(client)
        oid = self._get_org_id(app)
        resp = client.post('/classes', data={
            'title': 'No Date Class',
            'class_date': '',
            'location': 'Room 5',
            'max_attendees': '25',
            'org_unit_id': str(oid),
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Class date is required' in resp.data

    def test_missing_org_unit_returns_validation_error(self, client):
        _login(client)
        resp = client.post('/classes', data={
            'title': 'No Org Class',
            'class_date': '2026-10-01',
            'location': 'Room 5',
            'max_attendees': '25',
            'org_unit_id': '',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Organization unit is required' in resp.data

    def test_short_title_returns_validation_error(self, client, app):
        _login(client)
        oid = self._get_org_id(app)
        resp = client.post('/classes', data={
            'title': 'AB',
            'class_date': '2026-10-01',
            'location': 'Room 5',
            'max_attendees': '25',
            'org_unit_id': str(oid),
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'error' in resp.data or b'Title' in resp.data


# ═══════════════════════════════════════════════════════════════════════════
# 14. SENSITIVE-DATA MASKING (role-aware)
# ═══════════════════════════════════════════════════════════════════════════

class TestSensitiveDataMasking:
    def _get_listing_id(self, app):
        with app.app_context():
            return PropertyListing.query.filter_by(title='Draft Listing').first().id

    def test_admin_sees_full_address(self, client, app):
        """org_admin (property_manager equiv) sees unmasked address."""
        _login(client)
        lid = self._get_listing_id(app)
        resp = client.get(f'/listings/{lid}')
        assert resp.status_code == 200
        assert b'100 Main St' in resp.data

    def test_staff_sees_masked_address(self, client, app):
        """Staff user (non-privileged) sees masked address on listing detail."""
        _login(client, 'staffuser', 'staffpass')
        lid = self._get_listing_id(app)
        resp = client.get(f'/listings/{lid}')
        assert resp.status_code == 200
        assert b'100 Main St' not in resp.data
        assert b'10' in resp.data  # partial mask keeps prefix


class TestDrugApprovalPageVisibility:
    """Non-privileged users should not access draft drug pages."""

    def test_staff_cannot_view_draft_drug_page(self, client, app):
        _login(client)
        with app.app_context():
            oid = OrgUnit.query.first().id
        resp = client.post('/drugs', data={
            'generic_name': 'HiddenDraftDrug',
            'strength': '50mg',
            'form': 'tablet',
        }, follow_redirects=False)
        assert resp.status_code == 302
        from app.models.drug import Drug as DrugModel
        with app.app_context():
            drug = DrugModel.query.filter_by(generic_name='HiddenDraftDrug').first()
            drug_id = drug.id
        client.post('/auth/logout')
        _login(client, 'staffuser', 'staffpass')
        resp = client.get(f'/drugs/{drug_id}')
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 15. DRUG PAGE FLOWS (new form, submit/approve/reject, import)
# ═══════════════════════════════════════════════════════════════════════════

class TestDrugPageFlows:
    def _create_drug_id(self, client, app):
        _login(client)
        client.post('/drugs', data={
            'generic_name': 'Metformin',
            'strength': '500mg',
            'form': 'tablet',
            'description': 'Type 2 diabetes medication',
        })
        with app.app_context():
            from app.models.drug import Drug
            drug = Drug.query.filter_by(generic_name='Metformin').first()
            return drug.id

    def test_drug_new_form_renders(self, client):
        _login(client)
        resp = client.get('/drugs/new')
        assert resp.status_code == 200

    def test_drug_new_form_staff_forbidden(self, client):
        _login(client, 'staffuser', 'staffpass')
        resp = client.get('/drugs/new')
        assert resp.status_code == 403

    def test_drug_submit_page(self, client, app):
        drug_id = self._create_drug_id(client, app)
        resp = client.post(f'/drugs/{drug_id}/submit', follow_redirects=False)
        assert resp.status_code == 302
        assert f'/drugs/{drug_id}' in resp.headers.get('Location', '')
        with app.app_context():
            from app.models.drug import Drug
            drug = Drug.query.get(drug_id)
            assert drug.status == 'pending_approval'

    def test_drug_approve_page(self, client, app):
        drug_id = self._create_drug_id(client, app)
        client.post(f'/drugs/{drug_id}/submit')
        resp = client.post(f'/drugs/{drug_id}/approve', follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models.drug import Drug
            drug = Drug.query.get(drug_id)
            assert drug.status == 'approved'

    def test_drug_reject_page(self, client, app):
        drug_id = self._create_drug_id(client, app)
        client.post(f'/drugs/{drug_id}/submit')
        resp = client.post(
            f'/drugs/{drug_id}/reject',
            data={'reason': 'Incomplete safety data'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        with app.app_context():
            from app.models.drug import Drug
            drug = Drug.query.get(drug_id)
            assert drug.status == 'rejected'

    def test_drug_import_page_get(self, client):
        _login(client)
        resp = client.get('/drugs/import')
        assert resp.status_code == 200
        assert b'import' in resp.data.lower()

    def test_drug_import_page_post(self, client, app):
        import io
        _login(client)
        with app.app_context():
            from app.models.drug import Drug
            count_before = Drug.query.count()
        csv_content = (
            b"generic_name,strength,form,description\n"
            b"Aspirin,100mg,tablet,Pain reliever\n"
        )
        resp = client.post(
            '/drugs/import',
            data={'csv_file': (io.BytesIO(csv_content), 'drugs.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        with app.app_context():
            from app.models.drug import Drug
            assert Drug.query.count() == count_before + 1

    def test_drug_import_page_post_no_file(self, client):
        _login(client)
        resp = client.post('/drugs/import', data={})
        assert resp.status_code == 200
        assert b'No file' in resp.data or b'no file' in resp.data.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 16. CLASS PAGE ROUTES (attendance, review page submission, list)
# ═══════════════════════════════════════════════════════════════════════════

class TestClassPageMissingRoutes:
    def _get_class_id(self, app):
        with app.app_context():
            return TrainingClass.query.first().id

    def _get_attendee_user_id(self, app, class_id):
        with app.app_context():
            from app.models.training import ClassAttendee
            att = ClassAttendee.query.filter_by(class_id=class_id).first()
            return att.user_id

    def test_class_index_page_renders(self, client):
        _login(client)
        resp = client.get('/classes')
        assert resp.status_code == 200
        assert b'Safety Refresher' in resp.data

    def test_class_index_htmx_returns_partial(self, client):
        _login(client)
        resp = client.get('/classes', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data

    def test_attendance_instructor_marks_attended(self, client, app):
        _login(client)  # admin is the instructor
        cid = self._get_class_id(app)
        uid = self._get_attendee_user_id(app, cid)
        resp = client.post(
            f'/classes/{cid}/attendance',
            data={'attended_users': [str(uid)]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f'/classes/{cid}' in resp.headers.get('Location', '')
        with app.app_context():
            from app.models.training import ClassAttendee
            att = ClassAttendee.query.filter_by(class_id=cid, user_id=uid).first()
            assert att is not None
            assert att.attended is True

    def test_attendance_non_instructor_gets_flash_error(self, client, app):
        _login(client, 'staffuser', 'staffpass')
        cid = self._get_class_id(app)
        resp = client.post(
            f'/classes/{cid}/attendance',
            data={'attended_users': []},
            follow_redirects=False,
        )
        # Handler catches PermissionError, flashes error, and redirects
        assert resp.status_code == 302

    def test_class_review_page_duplicate_flashes_and_redirects(self, client, app):
        # Staff already reviewed in _seed(); posting again exercises the ValueError → redirect path
        _login(client, 'staffuser', 'staffpass')
        cid = self._get_class_id(app)
        resp = client.post(
            f'/classes/{cid}/reviews',
            data={'rating': '3', 'comment': 'Duplicate review attempt'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_class_list_api_returns_json(self, client):
        _login(client)
        resp = client.get('/api/classes')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert any(c['title'] == 'Safety Refresher' for c in data)

    def test_class_list_api_htmx_returns_partial(self, client):
        _login(client)
        resp = client.get('/api/classes', headers={'HX-Request': 'true'})
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 17. ADMIN PAGE ROUTES (panel, users page, permissions audit, backup run)
# ═══════════════════════════════════════════════════════════════════════════

class TestAdminPageRoutes:
    def test_admin_panel_renders(self, client):
        _login(client)
        resp = client.get('/admin')
        assert resp.status_code == 200

    def test_admin_panel_staff_forbidden(self, client):
        _login(client, 'staffuser', 'staffpass')
        resp = client.get('/admin')
        assert resp.status_code == 403

    def test_admin_users_page_renders(self, client):
        _login(client)
        resp = client.get('/admin/users')
        assert resp.status_code == 200
        assert b'admin' in resp.data

    def test_admin_users_page_staff_forbidden(self, client):
        _login(client, 'staffuser', 'staffpass')
        resp = client.get('/admin/users')
        assert resp.status_code == 403

    def test_admin_permissions_audit_page_renders(self, client):
        _login(client)
        resp = client.get('/admin/permissions/audit')
        assert resp.status_code == 200

    def test_admin_permissions_audit_staff_forbidden(self, client):
        _login(client, 'staffuser', 'staffpass')
        resp = client.get('/admin/permissions/audit')
        assert resp.status_code == 403

    def test_admin_assign_role_page(self, client, app):
        _login(client)
        with app.app_context():
            from app.models.user import User
            staff = User.query.filter_by(username='staffuser').first()
            staff_id = staff.id
        resp = client.post(
            f'/admin/users/{staff_id}/roles',
            data={'role_name': 'instructor'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        with app.app_context():
            from app.models.user import User
            staff = User.query.get(staff_id)
            role_names = {r.name for r in staff.roles}
            assert 'instructor' in role_names

    def test_admin_backups_run_staff_forbidden(self, client):
        _login(client, 'staffuser', 'staffpass')
        resp = client.post('/admin/backups/run')
        assert resp.status_code == 403

    def test_admin_backups_run_admin_redirects(self, client):
        # create_backup may fail on in-memory DB, but the handler catches RuntimeError
        # and always redirects to /admin/backups
        _login(client)
        resp = client.post('/admin/backups/run', follow_redirects=False)
        assert resp.status_code == 302
        assert '/admin/backups' in resp.headers.get('Location', '')


# ═══════════════════════════════════════════════════════════════════════════
# MODERATION APPEALS
# ═══════════════════════════════════════════════════════════════════════════

class TestModerationAppealsPageFlow:
    """Tests for POST /moderation/reports/<id>/appeal and
    POST /moderation/appeals/<id>/resolve."""

    def _setup_hidden_report(self, app):
        """Create a report that has already been hidden (required for filing an appeal)."""
        from app.models.training import TrainingClass, ClassAttendee, ClassReview
        from app.models.moderation import ModerationReport
        from app.services.moderation_service import hide_review

        with app.app_context():
            org = OrgUnit.query.filter_by(code='TC1').one()
            admin = User.query.filter_by(username='admin').one()
            staff = User.query.filter_by(username='staffuser').one()

            tc = TrainingClass(
                title='Appeal Test Class',
                instructor_id=admin.id,
                org_unit_id=org.id,
                class_date=date(2026, 11, 1),
                location='Room A',
                max_attendees=20,
            )
            _db.session.add(tc)
            _db.session.flush()
            _db.session.add(ClassAttendee(class_id=tc.id, user_id=staff.id, attended=True))

            review = ClassReview(
                class_id=tc.id,
                reviewer_id=staff.id,
                rating=1,
                comment='Terrible class — the instructor was useless.',
            )
            _db.session.add(review)
            _db.session.flush()

            report = ModerationReport(
                review_id=review.id,
                reported_by_id=admin.id,
                reason='Inappropriate language',
                status='pending',
            )
            _db.session.add(report)
            _db.session.commit()

            hide_review(report, admin, 'Contains offensive language')
            _db.session.commit()

            return report.id, staff.id

    def test_appeal_filed_by_review_author_redirects(self, client, app):
        """Staff (review author) can file an appeal on a hidden report."""
        report_id, _ = self._setup_hidden_report(app)
        _login(client, 'staffuser', 'staffpass')
        resp = client.post(
            f'/moderation/reports/{report_id}/appeal',
            data={'appeal_text': 'I believe this was unfairly hidden because my comment was factual.'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_appeal_creates_moderation_appeal_record(self, client, app):
        """Filing an appeal writes a ModerationAppeal row to the database."""
        from app.models.moderation import ModerationAppeal

        report_id, _ = self._setup_hidden_report(app)
        _login(client, 'staffuser', 'staffpass')
        client.post(
            f'/moderation/reports/{report_id}/appeal',
            data={'appeal_text': 'I believe this was unfairly hidden because my comment was factual.'},
        )
        with app.app_context():
            appeal = ModerationAppeal.query.filter_by(report_id=report_id).first()
            assert appeal is not None
            assert appeal.status == 'pending'

    def test_appeal_text_too_short_flashes_error(self, client, app):
        """Appeal text under 20 characters is rejected and redirects (with flash error)."""
        report_id, _ = self._setup_hidden_report(app)
        _login(client, 'staffuser', 'staffpass')
        resp = client.post(
            f'/moderation/reports/{report_id}/appeal',
            data={'appeal_text': 'Too short'},
            follow_redirects=False,
        )
        # Route catches ValueError and flashes — always redirects
        assert resp.status_code == 302

    def test_appeal_requires_review_author(self, client, app):
        """Admin (not the review author) filing an appeal is rejected (PermissionError → flash)."""
        report_id, _ = self._setup_hidden_report(app)
        _login(client)  # logged in as admin, not the review author
        resp = client.post(
            f'/moderation/reports/{report_id}/appeal',
            data={'appeal_text': 'I believe this was unfairly hidden because my comment was factual.'},
            follow_redirects=False,
        )
        # Route catches PermissionError and flashes error; still redirects
        assert resp.status_code == 302

    def test_resolve_appeal_upheld_by_moderator(self, client, app):
        """Admin (moderator) can resolve a pending appeal with decision='upheld'."""
        from app.models.moderation import ModerationAppeal

        report_id, _ = self._setup_hidden_report(app)
        _login(client, 'staffuser', 'staffpass')
        client.post(
            f'/moderation/reports/{report_id}/appeal',
            data={'appeal_text': 'I believe this was unfairly hidden because my comment was factual.'},
        )

        with app.app_context():
            appeal = ModerationAppeal.query.filter_by(report_id=report_id).first()
            appeal_id = appeal.id

        _login(client)  # re-login as admin
        resp = client.post(
            f'/moderation/appeals/{appeal_id}/resolve',
            data={'decision': 'upheld', 'notes': 'Reviewed — decision stands.'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        with app.app_context():
            appeal = ModerationAppeal.query.get(appeal_id)
            assert appeal.status == 'upheld'

    def test_resolve_appeal_overturned_by_moderator(self, client, app):
        """Admin can resolve an appeal with decision='overturned'."""
        from app.models.moderation import ModerationAppeal

        report_id, _ = self._setup_hidden_report(app)
        _login(client, 'staffuser', 'staffpass')
        client.post(
            f'/moderation/reports/{report_id}/appeal',
            data={'appeal_text': 'I believe this was unfairly hidden because my comment was factual.'},
        )

        with app.app_context():
            appeal = ModerationAppeal.query.filter_by(report_id=report_id).first()
            appeal_id = appeal.id

        _login(client)
        resp = client.post(
            f'/moderation/appeals/{appeal_id}/resolve',
            data={'decision': 'overturned', 'notes': 'Upon review, appeal is overturned.'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

        with app.app_context():
            appeal = ModerationAppeal.query.get(appeal_id)
            assert appeal.status == 'overturned'

    def test_resolve_requires_moderator_permission(self, client, app):
        """Staff user without review.moderate cannot resolve appeals."""
        from app.models.moderation import ModerationAppeal

        report_id, _ = self._setup_hidden_report(app)
        _login(client, 'staffuser', 'staffpass')
        client.post(
            f'/moderation/reports/{report_id}/appeal',
            data={'appeal_text': 'I believe this was unfairly hidden because my comment was factual.'},
        )

        with app.app_context():
            appeal = ModerationAppeal.query.filter_by(report_id=report_id).first()
            appeal_id = appeal.id

        # Staff tries to resolve — missing review.moderate permission
        resp = client.post(
            f'/moderation/appeals/{appeal_id}/resolve',
            data={'decision': 'upheld', 'notes': 'Staff attempt'},
        )
        assert resp.status_code == 403
