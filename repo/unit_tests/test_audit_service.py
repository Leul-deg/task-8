import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.services.audit_service import log_action, get_audit_logs, serialize_audit_log


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

    def test_sensitive_fields_are_masked_in_stored_payload(self, db):
        entry = log_action(
            action='user.register',
            resource_type='user',
            new_value={'email': 'alice@example.com', 'full_name': 'Alice Example', 'address_line1': '123 Main St'},
        )
        assert 'alice@example.com' not in entry.new_value
        assert 'Alice Example' not in entry.new_value
        assert '123 Main St' not in entry.new_value

    def test_serialize_audit_log_masks_existing_payloads(self, db):
        from app.models.audit import AuditLog
        entry = AuditLog(
            action='legacy.audit',
            resource_type='listing',
            new_value='{"address_line1": "123 Main St", "email": "legacy@example.com"}',
        )
        _db.session.add(entry)
        _db.session.commit()
        data = serialize_audit_log(entry)
        assert '123 Main St' not in data['new_value']
        assert 'legacy@example.com' not in data['new_value']
