from datetime import date

from app.models.drug import Drug
from app.models.listing import PropertyListing
from app.models.moderation import ModerationReport
from app.models.organization import OrgUnit
from app.models.training import TrainingClass, ClassReview
from app.models.user import User
from app.services.moderation_service import hide_review


def _login_admin(client):
    resp = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert resp.status_code == 200


def _create_listing(app, db, *, title='Component Listing'):
    with app.app_context():
        org = OrgUnit.query.filter_by(code='TC1').one()
        admin = User.query.filter_by(username='admin').one()
        listing = PropertyListing(
            title=title,
            address_line1='101 Frontend Way',
            city='Springfield',
            state='IL',
            zip_code='62701',
            monthly_rent_cents=150000,
            deposit_cents=50000,
            lease_start=date(2026, 7, 1),
            lease_end=date(2027, 6, 30),
            org_unit_id=org.id,
            created_by_id=admin.id,
            status='draft',
        )
        db.session.add(listing)
        db.session.commit()
        return listing.id


def _create_report(app, db):
    with app.app_context():
        org = OrgUnit.query.filter_by(code='TC1').one()
        admin = User.query.filter_by(username='admin').one()
        staff = User.query.filter_by(username='staffuser').one()
        training_class = TrainingClass(
            title='Component Test Class',
            instructor_id=admin.id,
            org_unit_id=org.id,
            class_date=date(2026, 8, 1),
            location='Room 10',
            max_attendees=20,
        )
        db.session.add(training_class)
        db.session.flush()
        review = ClassReview(
            class_id=training_class.id,
            reviewer_id=staff.id,
            rating=2,
            comment='This class was stupid and confusing for everyone.',
        )
        db.session.add(review)
        db.session.flush()
        report = ModerationReport(
            review_id=review.id,
            reported_by_id=admin.id,
            reason='Contains inappropriate language',
            status='pending',
        )
        db.session.add(report)
        db.session.commit()
        return report.id


class TestFrontendComponentPartials:
    def test_listing_grid_partial_renders_for_hx_request(self, client, app, db):
        listing_id = _create_listing(app, db, title='Grid Listing')
        assert listing_id is not None
        _login_admin(client)
        resp = client.get('/listings', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'Grid Listing' in resp.data
        assert b'<!DOCTYPE' not in resp.data
        assert b'listing-grid' in resp.data

    def test_listing_preview_partial_renders_modal_fragment(self, client, app, db):
        listing_id = _create_listing(app, db, title='Preview Listing')
        _login_admin(client)
        resp = client.get(f'/listings/{listing_id}/preview', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'Preview: Preview Listing' in resp.data
        assert b'modal' in resp.data
        assert b'<!DOCTYPE' not in resp.data

    def test_listing_status_htmx_returns_status_partial(self, client, app, db):
        listing_id = _create_listing(app, db, title='Status Listing')
        _login_admin(client)
        resp = client.post(
            f'/listings/{listing_id}/status',
            data={'status': 'pending_review'},
            headers={'HX-Request': 'true'},
        )
        assert resp.status_code == 200
        assert b'badge-pending_review' in resp.data or b'Pending Review' in resp.data
        assert b'status-card' in resp.data
        assert b'<!DOCTYPE' not in resp.data

    def test_moderation_queue_htmx_returns_report_list_partial(self, client, app, db):
        _create_report(app, db)
        _login_admin(client)
        resp = client.get('/moderation', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data
        # Report list partial — each card should have an id="report-N" attribute
        assert b'report-' in resp.data

    def test_moderation_hide_htmx_returns_updated_card_fragment(self, client, app, db):
        report_id = _create_report(app, db)
        _login_admin(client)
        resp = client.post(
            f'/moderation/reports/{report_id}/hide',
            data={'reason': 'Escalated'},
            headers={'HX-Request': 'true'},
        )
        assert resp.status_code == 200
        assert b'badge-review_hidden' in resp.data or b'Review Hidden' in resp.data
        assert b'id="report-' in resp.data
        assert b'<!DOCTYPE' not in resp.data


def _create_training_class(app, db):
    with app.app_context():
        org = OrgUnit.query.filter_by(code='TC1').one()
        admin = User.query.filter_by(username='admin').one()
        tc = TrainingClass(
            title='Fragment Test Class',
            instructor_id=admin.id,
            org_unit_id=org.id,
            class_date=date(2026, 9, 1),
            location='Hall B',
            max_attendees=25,
        )
        db.session.add(tc)
        db.session.commit()
        return tc.id


def _create_approved_drug(app, db):
    with app.app_context():
        admin = User.query.filter_by(username='admin').one()
        drug = Drug(
            generic_name='FragmentDrug',
            strength='200mg',
            form='tablet',
            status='approved',
            created_by_id=admin.id,
        )
        db.session.add(drug)
        db.session.commit()
        return drug.id


class TestAdminPartials:
    """HTMX partial fragments for admin pages."""

    def test_admin_user_table_partial(self, client, app, db):
        _login_admin(client)
        resp = client.get('/admin/users', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data
        # user-table partial must list at least the seeded admin user
        assert b'admin' in resp.data

    def test_admin_users_api_htmx_partial(self, client, app, db):
        _login_admin(client)
        resp = client.get('/api/admin/users', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data
        assert b'admin' in resp.data

    def test_admin_permissions_audit_htmx_partial(self, client, app, db):
        _login_admin(client)
        resp = client.get('/admin/permissions/audit', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data

    def test_admin_api_permissions_audit_htmx_partial(self, client, app, db):
        _login_admin(client)
        resp = client.get('/api/admin/permissions/audit', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data


class TestClassPartials:
    """HTMX partial fragments for class pages."""

    def test_class_list_page_htmx_partial(self, client, app, db):
        _create_training_class(app, db)
        _login_admin(client)
        resp = client.get('/classes', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data
        assert b'Fragment Test Class' in resp.data

    def test_class_list_api_htmx_partial(self, client, app, db):
        _create_training_class(app, db)
        _login_admin(client)
        resp = client.get('/api/classes', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data
        assert b'Fragment Test Class' in resp.data


class TestDrugPartials:
    """HTMX partial fragments for drug pages."""

    def test_drug_results_api_htmx_partial(self, client, app, db):
        _create_approved_drug(app, db)
        _login_admin(client)
        resp = client.get('/api/drugs?q=FragmentDrug', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data

    def test_drug_results_page_htmx_partial(self, client, app, db):
        _create_approved_drug(app, db)
        _login_admin(client)
        resp = client.get('/drugs?q=FragmentDrug', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'<!DOCTYPE' not in resp.data
