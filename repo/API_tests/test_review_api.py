import pytest
from datetime import date


@pytest.fixture
def training_class_id(db, client):
    from app.models.user import User
    from app.models.organization import OrgUnit
    from app.models.training import TrainingClass, ClassAttendee
    from app.extensions import db as _db
    org = OrgUnit.query.filter_by(code='TC1').first()
    instructor = User.query.filter_by(username='admin').first()
    staff = User.query.filter_by(username='staffuser').first()
    tc = TrainingClass(
        title='API Test Class',
        instructor_id=instructor.id,
        org_unit_id=org.id,
        class_date=date(2026, 8, 1),
        location='Hall A',
        max_attendees=50,
    )
    _db.session.add(tc)
    _db.session.flush()
    attendee = ClassAttendee(class_id=tc.id, user_id=staff.id, attended=True)
    _db.session.add(attendee)
    _db.session.commit()
    return tc.id


class TestReviewAPI:
    def test_create_review(self, client, training_class_id):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 4,
            'comment': 'Great class content and delivery!',
            'tags': ['engaging'],
        })
        assert resp.status_code == 201
        assert resp.get_json()['rating'] == 4

    def test_list_reviews(self, client, training_class_id):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get(f'/api/classes/{training_class_id}/reviews')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_duplicate_review(self, client, training_class_id):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 3,
            'comment': 'Decent class for all levels.',
        })
        resp = client.post(f'/api/classes/{training_class_id}/reviews', json={'rating': 5})
        assert resp.status_code == 400

    def test_unauthenticated_cannot_review(self, client, training_class_id):
        resp = client.post(f'/api/classes/{training_class_id}/reviews', json={'rating': 5})
        assert resp.status_code == 401

    def test_add_coach_reply(self, client, training_class_id):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        review_resp = client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 5,
            'comment': 'Excellent class well organized!',
        })
        review_id = review_resp.get_json()['id']
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post(f'/api/reviews/{review_id}/reply', json={'body': 'Thank you for the feedback!'})
        assert resp.status_code == 201

    def test_page_reply_requires_review_reply_permission(self, client, training_class_id):
        """Staff user without review.reply permission is denied on the page reply route."""
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        review_resp = client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 4,
            'comment': 'Solid class good examples used!',
        })
        review_id = review_resp.get_json()['id']
        resp = client.post(
            f'/classes/{training_class_id}/reviews/{review_id}/reply',
            data={'body': 'Sneaky reply attempt'},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_api_reply_requires_review_reply_permission(self, client, training_class_id):
        """Staff user without review.reply permission is denied on the API reply route."""
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        review_resp = client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 3,
            'comment': 'Decent class could be improved!',
        })
        review_id = review_resp.get_json()['id']
        resp = client.post(f'/api/reviews/{review_id}/reply', json={'body': 'Unauthorized reply attempt'})
        assert resp.status_code == 403

    def test_api_list_reviews_respects_org_display_mode(self, client, db, training_class_id):
        """API review listing must use the org's reviewer_display_mode, not default to anonymous."""
        from app.models.organization import OrgUnit
        from app.extensions import db as _db

        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 5,
            'comment': 'Display mode test review content here!',
        })

        org = OrgUnit.query.filter_by(code='TC1').first()
        org.reviewer_display_mode = 'full_name'
        _db.session.commit()

        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get(f'/api/classes/{training_class_id}/reviews')
        assert resp.status_code == 200
        reviews = resp.get_json()
        assert len(reviews) >= 1
        assert reviews[0]['reviewer_display'] != 'Anonymous Reviewer'
        assert reviews[0]['reviewer_display'] == 'Staff Member'

    def test_api_list_reviews_anonymous_mode(self, client, db, training_class_id):
        """With anonymous mode, reviewer names are hidden in API responses."""
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 4,
            'comment': 'Anonymous mode test review here!',
        })

        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get(f'/api/classes/{training_class_id}/reviews')
        reviews = resp.get_json()
        assert len(reviews) >= 1
        assert reviews[0]['reviewer_display'] == 'Anonymous Reviewer'

    def test_cross_org_user_denied_review_detail(self, client, db, training_class_id):
        """A user from a different org must not be able to fetch a review from another org."""
        from app.models.user import User, Role
        from app.models.organization import OrgUnit, UserOrgUnit
        from app.utils.constants import OrgUnitLevel
        from app.extensions import db as _db

        org2 = OrgUnit(name='Other Campus', code='TC2', level=OrgUnitLevel.CAMPUS.value)
        _db.session.add(org2)
        _db.session.flush()
        outsider = User(username='outsider', email='outsider@test.com', full_name='Outsider')
        outsider.set_password('outsider123')
        _db.session.add(outsider)
        _db.session.flush()
        staff_role = Role.query.filter_by(name='staff').first()
        outsider.roles.append(staff_role)
        _db.session.add(UserOrgUnit(user_id=outsider.id, org_unit_id=org2.id, is_primary=True))
        _db.session.commit()

        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        review_resp = client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 5,
            'comment': 'Cross-org isolation test review!',
        })
        assert review_resp.status_code == 201
        review_id = review_resp.get_json()['id']

        client.post('/auth/login', json={'username': 'outsider', 'password': 'outsider123'})
        resp = client.get(f'/api/reviews/{review_id}')
        assert resp.status_code == 403

    def test_cross_org_user_denied_review_update(self, client, db, training_class_id):
        """A user from a different org must not be able to update a review from another org."""
        from app.models.user import User, Role
        from app.models.organization import OrgUnit, UserOrgUnit
        from app.utils.constants import OrgUnitLevel
        from app.extensions import db as _db

        org2 = OrgUnit(name='Other Campus', code='OC2', level=OrgUnitLevel.CAMPUS.value)
        _db.session.add(org2)
        _db.session.flush()
        outsider = User(username='outsider2', email='outsider2@test.com', full_name='Outsider2')
        outsider.set_password('outsider123')
        _db.session.add(outsider)
        _db.session.flush()
        staff_role = Role.query.filter_by(name='staff').first()
        outsider.roles.append(staff_role)
        _db.session.add(UserOrgUnit(user_id=outsider.id, org_unit_id=org2.id, is_primary=True))
        _db.session.commit()

        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        review_resp = client.post(f'/api/classes/{training_class_id}/reviews', json={
            'rating': 3,
            'comment': 'Cross-org update isolation test!',
        })
        assert review_resp.status_code == 201
        review_id = review_resp.get_json()['id']

        client.post('/auth/login', json={'username': 'outsider2', 'password': 'outsider123'})
        resp = client.put(f'/api/reviews/{review_id}', json={'rating': 1, 'comment': 'Hijacked!'})
        assert resp.status_code == 403
