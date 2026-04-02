from datetime import date

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
