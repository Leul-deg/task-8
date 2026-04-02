import pytest
from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db as _db
from app.models.user import User, Role, Permission, TempGrant
from app.models.organization import OrgUnit, UserOrgUnit
from app.services.permission_service import has_permission, assign_role, remove_role, grant_temp_permission, revoke_temp_grant, expire_temp_grants


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
    u = User(username='tester', email='t@t.com')
    u.set_password('pass')
    r = Role(name='editor', is_system=False)
    p = Permission(codename='doc.edit', description='Edit', category='docs')
    _db.session.add_all([u, r, p])
    _db.session.commit()
    return u, r, p


class TestHasPermission:
    def test_via_role(self, db):
        u, r, p = _setup(db)
        r.permissions.append(p)
        u.roles.append(r)
        _db.session.commit()
        assert has_permission(u, 'doc.edit')

    def test_no_permission(self, db):
        u, r, p = _setup(db)
        assert not has_permission(u, 'doc.edit')

    def test_via_active_temp_grant(self, db):
        u, r, p = _setup(db)
        admin = User(username='admin2', email='a@a.com')
        admin.set_password('pass')
        _db.session.add(admin)
        _db.session.flush()
        grant = TempGrant(
            user_id=u.id,
            permission_id=p.id,
            granted_by_id=admin.id,
            reason='test',
            granted_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            is_active=True,
        )
        _db.session.add(grant)
        _db.session.commit()
        assert has_permission(u, 'doc.edit')

    def test_expired_temp_grant(self, db):
        u, r, p = _setup(db)
        admin = User(username='admin3', email='b@b.com')
        admin.set_password('pass')
        _db.session.add(admin)
        _db.session.flush()
        grant = TempGrant(
            user_id=u.id,
            permission_id=p.id,
            granted_by_id=admin.id,
            reason='old',
            granted_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            is_active=True,
        )
        _db.session.add(grant)
        _db.session.commit()
        assert not has_permission(u, 'doc.edit')


class TestOrgHierarchyPermission:
    def _make_org_hierarchy(self):
        """Returns (campus, college, dept, section) OrgUnit instances (flushed, not committed)."""
        from app.utils.constants import OrgUnitLevel
        campus = OrgUnit(name='Campus', code='CMP', level=OrgUnitLevel.CAMPUS.value)
        _db.session.add(campus)
        _db.session.flush()
        college = OrgUnit(name='College', code='COL', level=OrgUnitLevel.COLLEGE.value, parent_id=campus.id)
        _db.session.add(college)
        _db.session.flush()
        dept_a = OrgUnit(name='Dept A', code='DA', level=OrgUnitLevel.DEPARTMENT.value, parent_id=college.id)
        dept_b = OrgUnit(name='Dept B', code='DB', level=OrgUnitLevel.DEPARTMENT.value, parent_id=college.id)
        _db.session.add_all([dept_a, dept_b])
        _db.session.flush()
        return campus, college, dept_a, dept_b

    def _make_user_with_permission(self, codename='listing.create'):
        u = User(username=f'user_{codename.replace(".", "_")}', email=f'{codename}@t.com')
        u.set_password('Secret1!')
        r = Role(name=f'role_{codename.replace(".", "_")}', is_system=False)
        p = Permission.query.filter_by(codename=codename).first()
        if not p:
            p = Permission(codename=codename, description='test', category='test')
            _db.session.add(p)
        _db.session.add_all([u, r])
        _db.session.flush()
        r.permissions.append(p)
        u.roles.append(r)
        _db.session.flush()
        return u, p

    def test_campus_user_can_access_department(self, app):
        """A user assigned to campus can access department-level resources."""
        campus, college, dept_a, dept_b = self._make_org_hierarchy()
        u, p = self._make_user_with_permission('listing.create')
        _db.session.add(UserOrgUnit(user_id=u.id, org_unit_id=campus.id, is_primary=True))
        _db.session.commit()
        assert has_permission(u, 'listing.create', org_unit_id=dept_a.id) is True

    def test_department_user_cannot_access_sibling(self, app):
        """A user in Dept A cannot access Dept B resources."""
        campus, college, dept_a, dept_b = self._make_org_hierarchy()
        u, p = self._make_user_with_permission('listing.create')
        _db.session.add(UserOrgUnit(user_id=u.id, org_unit_id=dept_a.id, is_primary=True))
        _db.session.commit()
        assert has_permission(u, 'listing.create', org_unit_id=dept_b.id) is False

    def test_direct_org_membership_grants_access(self, app):
        """A user directly in a dept can access that dept's resources."""
        campus, college, dept_a, dept_b = self._make_org_hierarchy()
        u, p = self._make_user_with_permission('listing.create')
        _db.session.add(UserOrgUnit(user_id=u.id, org_unit_id=dept_a.id, is_primary=True))
        _db.session.commit()
        assert has_permission(u, 'listing.create', org_unit_id=dept_a.id) is True

    def test_no_org_membership_denies_org_scoped_check(self, app):
        """A user with the permission but no org membership is denied when org_unit_id given."""
        campus, college, dept_a, dept_b = self._make_org_hierarchy()
        u, p = self._make_user_with_permission('listing.create')
        _db.session.commit()
        assert has_permission(u, 'listing.create', org_unit_id=dept_a.id) is False

    def test_no_org_unit_id_skips_org_check(self, app):
        """Without org_unit_id the org check is skipped entirely."""
        campus, college, dept_a, dept_b = self._make_org_hierarchy()
        u, p = self._make_user_with_permission('listing.create')
        _db.session.commit()
        assert has_permission(u, 'listing.create') is True

    def test_cannot_remove_last_org_admin(self, app):
        """Removing the only active org_admin should raise ValueError."""
        admin_role = Role(name='org_admin', is_system=True)
        _db.session.add(admin_role)
        _db.session.flush()
        admin_user = User(username='sole_admin', email='sa@t.com')
        admin_user.set_password('Secret1!')
        _db.session.add(admin_user)
        _db.session.flush()
        admin_user.roles.append(admin_role)
        _db.session.commit()
        with pytest.raises(ValueError, match="last org_admin"):
            remove_role(admin_user, admin_role, admin_id=admin_user.id)


class TestSeedRoleDefaults:
    def test_instructor_has_class_create(self, app):
        """Instructor role must include class.create so instructors can manage classes out-of-box."""
        from scripts.seed_data import seed
        from app import _create_fts_table
        _create_fts_table(_db)
        seed()
        role = Role.query.filter_by(name='instructor').first()
        codenames = {p.codename for p in role.permissions}
        assert 'class.create' in codenames
        assert 'review.reply' in codenames


class TestGrantAndRevoke:
    def test_grant_temp_permission(self, db):
        u, r, p = _setup(db)
        admin = User(username='granter', email='g@g.com')
        admin.set_password('pass')
        _db.session.add(admin)
        _db.session.flush()
        grant = grant_temp_permission(u, p, admin, reason='emergency coverage', hours=24)
        assert grant.id is not None
        assert grant.is_active is True
        assert grant.expires_at > grant.granted_at

    def test_revoke_temp_grant(self, db):
        u, r, p = _setup(db)
        admin = User(username='revoker', email='rv@rv.com')
        admin.set_password('pass')
        _db.session.add(admin)
        _db.session.flush()
        grant = grant_temp_permission(u, p, admin, reason='test revoke', hours=1)
        revoke_temp_grant(grant, admin)
        assert grant.is_active is False


class TestExpireTempGrants:
    def test_deactivates_expired(self, db):
        u, r, p = _setup(db)
        admin = User(username='adminx', email='x@x.com')
        admin.set_password('pass')
        _db.session.add(admin)
        _db.session.flush()
        grant = TempGrant(
            user_id=u.id,
            permission_id=p.id,
            granted_by_id=admin.id,
            reason='expire me',
            granted_at=datetime.now(timezone.utc) - timedelta(hours=5),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            is_active=True,
        )
        _db.session.add(grant)
        _db.session.commit()
        count = expire_temp_grants()
        assert count == 1
        _db.session.refresh(grant)
        assert grant.is_active is False
