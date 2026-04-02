import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.services.audit_service import log_action, get_audit_logs


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


class TestAuditService:
    def test_log_action_creates_entry(self, db):
        entry = log_action(
            action='test.create',
            resource_type='test',
            resource_id=42,
            new_value={'key': 'value'},
        )
        assert entry.id is not None
        assert entry.action == 'test.create'
        assert entry.resource_id == 42

    def test_log_action_serializes_values(self, db):
        entry = log_action(
            action='test.update',
            resource_type='test',
            old_value={'x': 1},
            new_value={'x': 2},
        )
        assert '"x": 1' in entry.old_value
        assert '"x": 2' in entry.new_value

    def test_get_logs_filter_by_action(self, db):
        log_action(action='listing.create', resource_type='listing', resource_id=1)
        log_action(action='drug.create', resource_type='drug', resource_id=2)
        listing_logs = get_audit_logs(action='listing')
        assert all('listing' in l.action for l in listing_logs)

    def test_get_logs_filter_by_resource_type(self, db):
        log_action(action='x.create', resource_type='listing', resource_id=1)
        log_action(action='x.create', resource_type='drug', resource_id=2)
        logs = get_audit_logs(resource_type='listing')
        assert all(l.resource_type == 'listing' for l in logs)

    def test_system_action_no_user(self, db):
        entry = log_action(action='system.backup', resource_type='backup')
        assert entry.user_id is None
