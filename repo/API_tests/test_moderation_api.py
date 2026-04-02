import pytest
from datetime import date


@pytest.fixture
def review_id(db, client):
    from app.models.user import User
    from app.models.organization import OrgUnit
    from app.models.training import TrainingClass, ClassAttendee
    from app.extensions import db as _db
    from app.services.review_service import create_review
    org = OrgUnit.query.filter_by(code='TC1').first()
    instructor = User.query.filter_by(username='admin').first()
    staff = User.query.filter_by(username='staffuser').first()
    tc = TrainingClass(
        title='Mod Test Class',
        instructor_id=instructor.id,
        org_unit_id=org.id,
        class_date=date(2026, 9, 1),
        location='Room 3',
        max_attendees=20,
    )
    _db.session.add(tc)
    _db.session.flush()
    attendee = ClassAttendee(class_id=tc.id, user_id=staff.id, attended=True)
    _db.session.add(attendee)
    _db.session.commit()
    review = create_review(tc.id, staff, {'rating': 1, 'comment': 'Absolute waste of time entirely!'})
    return review.id


class TestModerationAPI:
    def test_report_review(self, client, review_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/moderation/reports', json={
            'review_id': review_id,
            'reason': 'Inappropriate language',
        })
        assert resp.status_code == 201
        return resp.get_json()['id']

    def test_hide_review(self, client, review_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        report_resp = client.post('/api/moderation/reports', json={
            'review_id': review_id,
            'reason': 'Spam content',
        })
        report_id = report_resp.get_json()['id']
        resp = client.post(f'/api/moderation/reports/{report_id}/hide', json={'reason': 'spam'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'review_hidden'

    def test_restore_review(self, client, review_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        report_resp = client.post('/api/moderation/reports', json={
            'review_id': review_id,
            'reason': 'Spam content',
        })
        report_id = report_resp.get_json()['id']
        client.post(f'/api/moderation/reports/{report_id}/hide', json={'reason': 'spam'})
        resp = client.post(f'/api/moderation/reports/{report_id}/restore')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'review_restored'

    def test_file_appeal(self, client, review_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        report_resp = client.post('/api/moderation/reports', json={
            'review_id': review_id,
            'reason': 'Spam content',
        })
        report_id = report_resp.get_json()['id']
        client.post(f'/api/moderation/reports/{report_id}/hide', json={'reason': 'spam'})
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.post('/api/moderation/appeals', json={
            'report_id': report_id,
            'appeal_text': 'My review was completely valid and factual, please reconsider this decision',
        })
        assert resp.status_code == 201
        assert resp.get_json()['status'] == 'pending'

    def test_non_author_appeal_returns_403(self, client, review_id):
        """Only the review author can file an appeal — admin is not the author."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        report_resp = client.post('/api/moderation/reports', json={
            'review_id': review_id,
            'reason': 'Spam content',
        })
        report_id = report_resp.get_json()['id']
        client.post(f'/api/moderation/reports/{report_id}/hide', json={'reason': 'spam'})
        # Admin is NOT the review author (staffuser is) — appeal must be rejected
        resp = client.post('/api/moderation/appeals', json={
            'report_id': report_id,
            'appeal_text': 'I should not be allowed to appeal this review since I did not write it',
        })
        assert resp.status_code == 403
        assert 'author' in resp.get_json()['error'].lower()

    def test_report_requires_auth(self, client, review_id):
        resp = client.post('/api/moderation/reports', json={
            'review_id': review_id,
            'reason': 'test',
        })
        assert resp.status_code == 401
