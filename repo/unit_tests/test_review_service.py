import pytest
from datetime import date
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.organization import OrgUnit, UserOrgUnit
from app.models.training import TrainingClass, ClassAttendee
from app.services.review_service import (
    create_review, update_review, add_coach_reply, update_coach_reply, format_reviewer_name,
)
from app.utils.constants import OrgUnitLevel


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
    instructor = User(username='instructor1', email='i@t.com')
    instructor.set_password('pass')
    student = User(username='student1', email='s@t.com')
    student.set_password('pass')
    org = OrgUnit(name='Test', code='T1', level=OrgUnitLevel.CAMPUS.value)
    _db.session.add_all([instructor, student, org])
    _db.session.flush()
    tc = TrainingClass(
        title='Flask 101',
        instructor_id=instructor.id,
        org_unit_id=org.id,
        class_date=date(2026, 4, 1),
        location='Room 1',
        max_attendees=30,
    )
    _db.session.add(tc)
    _db.session.flush()
    attendee = ClassAttendee(class_id=tc.id, user_id=student.id, attended=True)
    _db.session.add(attendee)
    _db.session.add_all([
        UserOrgUnit(user_id=instructor.id, org_unit_id=org.id, is_primary=True),
        UserOrgUnit(user_id=student.id, org_unit_id=org.id, is_primary=True),
    ])
    _db.session.commit()
    return instructor, student, tc


class TestCreateReview:
    def test_creates_review(self, db):
        instructor, student, tc = _setup(db)
        review = create_review(tc.id, student, {'rating': 4, 'tags': ['engaging'], 'comment': 'Very good class overall!'})
        assert review.id is not None
        assert review.rating == 4

    def test_duplicate_review_raises(self, db):
        instructor, student, tc = _setup(db)
        create_review(tc.id, student, {'rating': 3, 'comment': 'Decent class for beginners!'})
        with pytest.raises(ValueError, match='already reviewed'):
            create_review(tc.id, student, {'rating': 5})

    def test_invalid_rating_raises(self, db):
        instructor, student, tc = _setup(db)
        with pytest.raises(ValueError):
            create_review(tc.id, student, {'rating': 6})

    def test_comment_too_short_raises(self, db):
        instructor, student, tc = _setup(db)
        with pytest.raises(ValueError, match='20 characters'):
            create_review(tc.id, student, {'rating': 3, 'comment': 'Short'})

    def test_too_many_tags_raises(self, db):
        instructor, student, tc = _setup(db)
        with pytest.raises(ValueError, match='5 tags'):
            create_review(tc.id, student, {
                'rating': 4,
                'tags': ['engaging', 'clear_instructions', 'practical', 'well_organized', 'great_instructor', 'too_fast'],
            })

    def test_create_review_non_attendee(self, db):
        instructor, student, tc = _setup(db)
        non_attendee = User(username='outsider', email='o@t.com')
        non_attendee.set_password('pass')
        _db.session.add(non_attendee)
        _db.session.flush()
        _db.session.add(UserOrgUnit(user_id=non_attendee.id, org_unit_id=tc.org_unit_id, is_primary=True))
        _db.session.commit()
        with pytest.raises(PermissionError, match='verified attendees'):
            create_review(tc.id, non_attendee, {'rating': 4, 'comment': 'Trying to review without attending!'})


class TestCoachReply:
    def test_add_reply(self, db):
        instructor, student, tc = _setup(db)
        review = create_review(tc.id, student, {'rating': 5, 'comment': 'Excellent class materials!'})
        reply = add_coach_reply(review, instructor, 'Thank you!')
        assert reply.id is not None

    def test_duplicate_reply_raises(self, db):
        instructor, student, tc = _setup(db)
        review = create_review(tc.id, student, {'rating': 5, 'comment': 'Excellent class materials!'})
        add_coach_reply(review, instructor, 'First reply')
        with pytest.raises(ValueError, match='already exists'):
            add_coach_reply(review, instructor, 'Second reply')

    def test_add_reply_non_instructor_raises(self, db):
        instructor, student, tc = _setup(db)
        other = User(username='other_instr', email='oi@t.com')
        other.set_password('pass')
        _db.session.add(other)
        _db.session.commit()
        review = create_review(tc.id, student, {'rating': 4, 'comment': 'Good class experience overall!'})
        with pytest.raises(PermissionError, match='class instructor'):
            add_coach_reply(review, other, 'Unauthorized reply')

    def test_update_reply_wrong_instructor(self, db):
        instructor, student, tc = _setup(db)
        other = User(username='other_instr', email='oi@t.com')
        other.set_password('pass')
        _db.session.add(other)
        _db.session.commit()
        review = create_review(tc.id, student, {'rating': 4, 'comment': 'Good class experience overall!'})
        reply = add_coach_reply(review, instructor, 'Thanks!')
        with pytest.raises(PermissionError, match="another instructor"):
            update_coach_reply(reply, other, 'Overwriting')


class TestReviewerDisplay:
    def test_display_anonymous(self, db):
        instructor, student, tc = _setup(db)
        name = format_reviewer_name(student, 'anonymous')
        assert name == 'Anonymous Reviewer'

    def test_display_initials(self, db):
        instructor, student, tc = _setup(db)
        student.full_name = 'Jane Doe'
        _db.session.commit()
        name = format_reviewer_name(student, 'initials')
        assert name == 'J.D.'

    def test_display_full_name(self, db):
        instructor, student, tc = _setup(db)
        student.full_name = 'Jane Doe'
        _db.session.commit()
        name = format_reviewer_name(student, 'full_name')
        assert name == 'Jane Doe'
