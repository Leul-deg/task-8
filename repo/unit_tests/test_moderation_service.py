import pytest
from datetime import date, datetime, timezone, timedelta
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.organization import OrgUnit
from app.models.training import TrainingClass, ClassAttendee
from app.services.review_service import create_review
from app.services.moderation_service import (
    report_review, hide_review, restore_review, file_appeal, resolve_appeal,
    scan_review_content, auto_flag_review, finalize_report,
)
from app.utils.constants import OrgUnitLevel, ModerationStatus, AppealStatus


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
    instructor = User(username='instr2', email='instr2@t.com')
    instructor.set_password('pass')
    student = User(username='stud2', email='stud2@t.com')
    student.set_password('pass')
    moderator = User(username='mod1', email='mod1@t.com')
    moderator.set_password('pass')
    org = OrgUnit(name='Org2', code='O2', level=OrgUnitLevel.CAMPUS.value)
    _db.session.add_all([instructor, student, moderator, org])
    _db.session.flush()
    tc = TrainingClass(
        title='Safety Training',
        instructor_id=instructor.id,
        org_unit_id=org.id,
        class_date=date(2026, 5, 1),
        location='Room 2',
        max_attendees=20,
    )
    _db.session.add(tc)
    _db.session.flush()
    attendee = ClassAttendee(class_id=tc.id, user_id=student.id, attended=True)
    _db.session.add(attendee)
    _db.session.commit()
    review = create_review(tc.id, student, {'rating': 1, 'comment': 'Truly terrible experience overall!'})
    return student, moderator, review


class TestScanContent:
    def test_scan_clean_text(self, db):
        result = scan_review_content('Very good class overall!')
        assert result['flagged'] is False
        assert result['matches'] == []

    def test_scan_blocked_keyword(self, db):
        result = scan_review_content('The instructor is an idiot and incompetent')
        assert result['flagged'] is True
        assert 'idiot' in result['matches']

    def test_scan_empty_text(self, db):
        result = scan_review_content('')
        assert result['flagged'] is False


class TestAutoFlag:
    def test_auto_flag_hides_review(self, db):
        student, moderator, review = _setup(db)
        review.comment = 'This class was absolutely stupid and a waste of time'
        _db.session.commit()
        report = auto_flag_review(review.id)
        assert report is not None
        _db.session.refresh(review)
        assert review.is_visible is False

    def test_auto_flag_clean_review_returns_none(self, db):
        student, moderator, review = _setup(db)
        result = auto_flag_review(review.id)
        assert result is None


class TestModerationReport:
    def test_report_review(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Inappropriate content here')
        assert report.id is not None
        assert report.status == ModerationStatus.PENDING.value

    def test_hide_review(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Spam content here')
        hide_review(report, moderator, 'Contains spam')
        assert report.status == ModerationStatus.REVIEW_HIDDEN.value
        assert review.is_visible is False

    def test_restore_review(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Spam content here')
        hide_review(report, moderator)
        restore_review(report, moderator)
        assert review.is_visible is True
        assert report.status == ModerationStatus.REVIEW_RESTORED.value

    def test_duplicate_report_fails(self, db):
        student, moderator, review = _setup(db)
        report_review(review, moderator, 'Inappropriate content here')
        with pytest.raises(ValueError, match='already reported'):
            report_review(review, moderator, 'Duplicate report attempt here')

    def test_report_reason_too_short(self, db):
        student, moderator, review = _setup(db)
        with pytest.raises(ValueError, match='10-500 characters'):
            report_review(review, moderator, 'Bad')

    def test_finalize_report(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Spam content here')
        finalize_report(report, moderator)
        assert report.status == ModerationStatus.FINALIZED.value
        assert report.resolved_by_id == moderator.id


class TestAppeal:
    def test_file_appeal(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Spam content here')
        hide_review(report, moderator)
        appeal = file_appeal(report, student, 'My review was valid, please reconsider')
        assert appeal.id is not None
        assert appeal.status == AppealStatus.PENDING.value
        assert appeal.deadline > appeal.filed_at

    def test_resolve_appeal_overturned(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Spam content here')
        hide_review(report, moderator)
        appeal = file_appeal(report, student, 'Please reconsider this decision')
        resolve_appeal(appeal, moderator, AppealStatus.OVERTURNED.value, 'Review was valid')
        assert appeal.status == AppealStatus.OVERTURNED.value
        assert review.is_visible is True

    def test_resolve_appeal_upheld(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Spam content here')
        hide_review(report, moderator)
        appeal = file_appeal(report, student, 'My review was valid, please reconsider this decision')
        resolve_appeal(appeal, moderator, AppealStatus.UPHELD.value, 'Content was inappropriate')
        assert appeal.status == AppealStatus.UPHELD.value
        assert review.is_visible is False  # still hidden when upheld

    def test_file_appeal_past_deadline(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Spam content here')
        hide_review(report, moderator)
        report.resolved_at = datetime.now(timezone.utc) - timedelta(days=15)
        _db.session.commit()
        with pytest.raises(ValueError, match='expired'):
            file_appeal(report, student, 'My review was valid, please reconsider this')

    def test_file_appeal_non_author(self, db):
        student, moderator, review = _setup(db)
        report = report_review(review, moderator, 'Spam content here')
        hide_review(report, moderator)
        with pytest.raises(PermissionError, match='Only the review author'):
            file_appeal(report, moderator, 'My review was valid, please reconsider this!')
