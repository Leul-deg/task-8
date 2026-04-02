import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User, Role, Permission
from app.models.organization import OrgUnit, UserOrgUnit
from app.utils.constants import OrgUnitLevel, DEFAULT_PERMISSIONS, DEFAULT_ROLES


@pytest.fixture(scope='function')
def app():
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        _seed_base_data()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


def _seed_base_data():
    # Permissions
    perms = {}
    for pdata in DEFAULT_PERMISSIONS:
        p = Permission(**pdata)
        _db.session.add(p)
        perms[pdata['codename']] = p
    _db.session.flush()

    # Roles
    roles = {}
    for rdata in DEFAULT_ROLES:
        r = Role(**rdata)
        _db.session.add(r)
        roles[rdata['name']] = r
    _db.session.flush()

    # Give org_admin all permissions
    for p in perms.values():
        roles['org_admin'].permissions.append(p)

    # Default org unit
    org = OrgUnit(name='Test Campus', code='TC1', level=OrgUnitLevel.CAMPUS.value)
    _db.session.add(org)
    _db.session.flush()

    # Admin user
    admin = User(username='admin', email='admin@test.com', full_name='Admin User')
    admin.set_password('admin123')
    _db.session.add(admin)
    _db.session.flush()
    admin.roles.append(roles['org_admin'])
    _db.session.add(UserOrgUnit(user_id=admin.id, org_unit_id=org.id, is_primary=True))

    # Assign instructor role permissions
    for codename in ['class.create', 'review.reply']:
        roles['instructor'].permissions.append(perms[codename])

    # Assign staff role permissions
    for codename in ['review.create', 'listing.create']:
        roles['staff'].permissions.append(perms[codename])

    # Staff user
    staff = User(username='staffuser', email='staff@test.com', full_name='Staff Member')
    staff.set_password('staffpass')
    _db.session.add(staff)
    _db.session.flush()
    staff.roles.append(roles['staff'])
    _db.session.add(UserOrgUnit(user_id=staff.id, org_unit_id=org.id, is_primary=True))

    _db.session.commit()


@pytest.fixture
def admin_headers(client):
    resp = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert resp.status_code == 200
    return {'Content-Type': 'application/json'}


@pytest.fixture
def staff_headers(client):
    resp = client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
    assert resp.status_code == 200
    return {'Content-Type': 'application/json'}
