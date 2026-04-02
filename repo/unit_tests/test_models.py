import os
import re
import pytest
from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db as _db
from app.models.user import User, Role, Permission, TempGrant
from app.models.organization import OrgUnit
from app.models.listing import PropertyListing
from app.models.drug import Drug
from app.models.audit import AuditLog
from app.utils.constants import OrgUnitLevel, ListingStatus, DrugStatus, DrugForm


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


def _make_user(username='testuser', password='password123'):
    u = User(username=username, email=f'{username}@test.com', full_name='Test User')
    u.set_password(password)
    return u


class TestUser:
    def test_password_hashing(self, db):
        u = _make_user()
        assert u.check_password('password123')
        assert not u.check_password('wrong')

    def test_display_name_full(self, db):
        u = _make_user()
        u.display_preference = 'full_name'
        u.full_name = 'Jane Doe'
        assert u.get_display_name() == 'Jane Doe'

    def test_display_name_initials(self, db):
        u = _make_user()
        u.display_preference = 'initials'
        u.full_name = 'Jane Doe'
        assert u.get_display_name() == 'JD'

    def test_display_name_anonymous(self, db):
        u = _make_user()
        u.display_preference = 'anonymous'
        assert u.get_display_name() == 'Anonymous'

    def test_to_dict(self, db):
        u = _make_user()
        _db.session.add(u)
        _db.session.commit()
        d = u.to_dict()
        assert d['username'] == 'testuser'
        assert 'password_hash' not in d

    def test_is_active_default(self, db):
        u = _make_user()
        assert u.is_active is True


class TestRole:
    def test_create_role(self, db):
        r = Role(name='test_role', description='Test', is_system=False)
        _db.session.add(r)
        _db.session.commit()
        assert r.id is not None

    def test_role_permission_relationship(self, db):
        r = Role(name='editor', is_system=False)
        p = Permission(codename='doc.edit', description='Edit docs', category='docs')
        _db.session.add_all([r, p])
        _db.session.commit()
        r.permissions.append(p)
        _db.session.commit()
        assert p in list(r.permissions)


class TestOrgUnit:
    def test_hierarchy(self, db):
        campus = OrgUnit(name='Main Campus', code='MC', level=OrgUnitLevel.CAMPUS.value)
        _db.session.add(campus)
        _db.session.flush()
        college = OrgUnit(name='Medicine', code='MED', level=OrgUnitLevel.COLLEGE.value, parent_id=campus.id)
        _db.session.add(college)
        _db.session.commit()
        assert college.parent.name == 'Main Campus'
        assert college in campus.get_descendants()
        assert campus in college.get_ancestors()


class TestPropertyListing:
    def test_monetary_values_in_cents(self, db):
        u = _make_user()
        _db.session.add(u)
        org = OrgUnit(name='OU', code='OU1', level=OrgUnitLevel.CAMPUS.value)
        _db.session.add(org)
        _db.session.flush()
        from datetime import date
        listing = PropertyListing(
            title='Test Apt',
            address_line1='123 Main St',
            city='Anytown',
            state='CA',
            zip_code='90210',
            monthly_rent_cents=150000,
            deposit_cents=300000,
            lease_start=date(2026, 1, 1),
            lease_end=date(2026, 12, 31),
            created_by_id=u.id,
            org_unit_id=org.id,
        )
        _db.session.add(listing)
        _db.session.commit()
        assert listing.monthly_rent_cents == 150000
        assert listing.status == ListingStatus.DRAFT.value


class TestDrug:
    def test_unique_constraint(self, db):
        u = _make_user()
        _db.session.add(u)
        _db.session.flush()
        d1 = Drug(generic_name='Aspirin', strength='81mg', form=DrugForm.TABLET.value, created_by_id=u.id)
        d2 = Drug(generic_name='Aspirin', strength='81mg', form=DrugForm.TABLET.value, created_by_id=u.id)
        _db.session.add(d1)
        _db.session.commit()
        _db.session.add(d2)
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            _db.session.commit()


class TestAuditLog:
    def test_no_update_method(self):
        assert not hasattr(AuditLog, 'update')

    def test_no_delete_method(self):
        assert not hasattr(AuditLog, 'delete')

    def test_create_audit_log(self, db):
        log = AuditLog(action='test.action', resource_type='test', resource_id=1)
        _db.session.add(log)
        _db.session.commit()
        assert log.id is not None
        assert log.timestamp is not None


class TestHtmxArchitectureFit:
    """Browser HTMX calls should target REST-style /api/ endpoints."""

    _HX_ATTR_RE = re.compile(r'hx-(?:get|post|put|delete|patch)="([^"]+)"')
    _ALLOWED_PREFIXES = ('/auth/', '/api/', '?')

    def _collect_htmx_urls(self):
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'templates')
        violations = []
        for root, _dirs, files in os.walk(template_dir):
            for fname in files:
                if not fname.endswith('.html'):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    for lineno, line in enumerate(f, 1):
                        for m in self._HX_ATTR_RE.finditer(line):
                            url = m.group(1)
                            if url.startswith(('http://', 'https://', '//')):
                                rel = os.path.relpath(fpath, template_dir)
                                violations.append(f'{rel}:{lineno} -> external URL {url}')
                                continue
                            if not any(url.startswith(p) for p in self._ALLOWED_PREFIXES):
                                rel = os.path.relpath(fpath, template_dir)
                                violations.append(f'{rel}:{lineno} -> {url}')
        return violations

    def test_all_htmx_calls_target_api_or_auth_endpoints(self):
        violations = self._collect_htmx_urls()
        assert violations == [], (
            'HTMX attributes must target API/auth endpoints, but found:\n'
            + '\n'.join(violations)
        )
