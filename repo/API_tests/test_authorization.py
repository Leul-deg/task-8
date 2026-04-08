"""Cross-user and cross-org-unit authorization tests.

Verifies that object-level (listing) and org-unit-scoped permission checks
are enforced correctly at the route layer, not just at the permission-service
level.
"""
import pytest
from datetime import date

from app import create_app
from app.extensions import db as _db
from app.models.user import User, Role, Permission
from app.models.organization import OrgUnit, UserOrgUnit
from app.utils.constants import OrgUnitLevel, DEFAULT_PERMISSIONS, DEFAULT_ROLES


# ---------------------------------------------------------------------------
# Fixtures — two org units, three users
# ---------------------------------------------------------------------------

@pytest.fixture(scope='class')
def app():
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        _seed()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _seed():
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

    # org_admin gets all permissions
    for p in perms.values():
        roles['org_admin'].permissions.append(p)

    # property_manager gets listing permissions
    for codename in ['listing.create', 'listing.edit', 'listing.publish',
                     'listing.delete', 'listing.lock']:
        roles['property_manager'].permissions.append(perms[codename])

    # instructor gets class.create + review.reply
    for codename in ['class.create', 'review.reply']:
        roles['instructor'].permissions.append(perms[codename])

    # Two org units
    tc1 = OrgUnit(name='Campus One', code='TC1', level=OrgUnitLevel.CAMPUS.value)
    tc2 = OrgUnit(name='Campus Two', code='TC2', level=OrgUnitLevel.CAMPUS.value)
    _db.session.add_all([tc1, tc2])
    _db.session.flush()

    # admin — org_admin scoped to TC1
    admin = User(username='admin', email='admin@test.com', full_name='Admin')
    admin.set_password('admin123')
    _db.session.add(admin)
    _db.session.flush()
    admin.roles.append(roles['org_admin'])
    _db.session.add(UserOrgUnit(user_id=admin.id, org_unit_id=tc1.id, is_primary=True))

    # mgr_tc1 — property_manager in TC1
    mgr1 = User(username='mgr_tc1', email='mgr1@test.com', full_name='Manager TC1')
    mgr1.set_password('Manager1!')
    _db.session.add(mgr1)
    _db.session.flush()
    mgr1.roles.append(roles['property_manager'])
    _db.session.add(UserOrgUnit(user_id=mgr1.id, org_unit_id=tc1.id, is_primary=True))

    # mgr_tc2 — property_manager in TC2 only
    mgr2 = User(username='mgr_tc2', email='mgr2@test.com', full_name='Manager TC2')
    mgr2.set_password('Manager2!')
    _db.session.add(mgr2)
    _db.session.flush()
    mgr2.roles.append(roles['property_manager'])
    _db.session.add(UserOrgUnit(user_id=mgr2.id, org_unit_id=tc2.id, is_primary=True))

    # instructor_tc1 — instructor in TC1 (can create classes)
    instr = User(username='instr_tc1', email='instr1@test.com', full_name='Instructor TC1')
    instr.set_password('Instr123!')
    _db.session.add(instr)
    _db.session.flush()
    instr.roles.append(roles['instructor'])
    _db.session.add(UserOrgUnit(user_id=instr.id, org_unit_id=tc1.id, is_primary=True))

    # unprivileged — staff role, no listing.edit, member of TC1
    unpriv = User(username='unpriv', email='unpriv@test.com', full_name='No Perms')
    unpriv.set_password('Unpriv123!')
    _db.session.add(unpriv)
    _db.session.flush()
    roles['staff'].permissions.append(perms['listing.create'])
    unpriv.roles.append(roles['staff'])
    _db.session.add(UserOrgUnit(user_id=unpriv.id, org_unit_id=tc1.id, is_primary=True))

    _db.session.commit()


def _listing_payload(org_unit_id):
    return {
        'title': 'Test Apt',
        'address_line1': '1 Main St',
        'city': 'Chicago',
        'state': 'IL',
        'zip_code': '60601',
        'monthly_rent_cents': 80000,
        'deposit_cents': 80000,
        'lease_start': str(date.today()),
        'lease_end': str(date.today().replace(year=date.today().year + 1)),
        'org_unit_id': org_unit_id,
    }


def _org_id(code):
    return OrgUnit.query.filter_by(code=code).one().id


# ---------------------------------------------------------------------------
# Listing read paths — org-unit isolation
# ---------------------------------------------------------------------------

class TestListingReadAuthorization:
    """Users must not be able to read listings outside their org hierarchy."""

    def _create_listing_as(self, client, username, password, org_code):
        client.post('/auth/login', json={'username': username, 'password': password})
        with client.application.app_context():
            org_id = _org_id(org_code)
        create = client.post('/api/listings', json=_listing_payload(org_id))
        assert create.status_code == 201
        lid = create.get_json()['id']
        client.post('/auth/logout')
        return lid

    def test_user_can_read_own_org_listing(self, client):
        """mgr_tc1 can GET a TC1 listing."""
        lid = self._create_listing_as(client, 'mgr_tc1', 'Manager1!', 'TC1')
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        assert client.get(f'/api/listings/{lid}').status_code == 200

    def test_user_cannot_read_other_org_listing(self, client):
        """mgr_tc2 (TC2) cannot GET a TC1 listing."""
        lid = self._create_listing_as(client, 'mgr_tc1', 'Manager1!', 'TC1')
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        assert client.get(f'/api/listings/{lid}').status_code == 403

    def test_list_scoped_to_user_org(self, client):
        """list_listings returns only listings in the user's org scope."""
        # mgr_tc1 creates a TC1 listing; mgr_tc2 creates a TC2 listing
        self._create_listing_as(client, 'mgr_tc1', 'Manager1!', 'TC1')
        self._create_listing_as(client, 'mgr_tc2', 'Manager2!', 'TC2')

        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        items = client.get('/api/listings').get_json()
        with client.application.app_context():
            tc1_id = _org_id('TC1')
        assert all(item['org_unit_id'] == tc1_id for item in items)

    def test_list_cross_org_filter_denied(self, client):
        """Requesting ?org_unit_id outside the user's scope returns 403."""
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        with client.application.app_context():
            tc2_id = _org_id('TC2')
        resp = client.get(f'/api/listings?org_unit_id={tc2_id}')
        assert resp.status_code == 403

    def test_page_detail_cross_org_denied(self, client):
        """Detail page for a cross-org listing returns 403."""
        lid = self._create_listing_as(client, 'mgr_tc1', 'Manager1!', 'TC1')
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        assert client.get(f'/listings/{lid}').status_code == 403

    def test_page_index_scoped_to_user_org(self, client):
        """The page index only renders listings the user can access."""
        self._create_listing_as(client, 'mgr_tc1', 'Manager1!', 'TC1')
        self._create_listing_as(client, 'mgr_tc2', 'Manager2!', 'TC2')
        # mgr_tc2 should not see TC1 listing in page index (no 403 — just filtered)
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.get('/listings')
        assert resp.status_code == 200
        # TC1 address/title must not appear in the rendered HTML
        assert b'Studio Apt' not in resp.data or resp.data.count(b'Studio Apt') == 1


# ---------------------------------------------------------------------------
# Listing edit (PUT) — org-unit isolation
# ---------------------------------------------------------------------------

class TestListingEditAuthorization:
    def test_owner_org_can_edit(self, client):
        """mgr_tc1 creates and edits a TC1 listing — should succeed."""
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        create = client.post('/api/listings', json=_listing_payload(org_id))
        assert create.status_code == 201
        lid = create.get_json()['id']

        resp = client.put(f'/api/listings/{lid}', json={'title': 'Updated'})
        assert resp.status_code == 200
        assert resp.get_json()['title'] == 'Updated'

    def test_cross_org_edit_denied(self, client):
        """mgr_tc2 (TC2 only) cannot edit a TC1 listing."""
        # Admin creates a TC1 listing
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        create = client.post('/api/listings', json=_listing_payload(org_id))
        assert create.status_code == 201
        lid = create.get_json()['id']
        client.post('/auth/logout')

        # mgr_tc2 (TC2) tries to edit it
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.put(f'/api/listings/{lid}', json={'title': 'Hijacked'})
        assert resp.status_code == 403

    def test_no_permission_edit_denied(self, client):
        """User with no listing.edit permission is denied."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        create = client.post('/api/listings', json=_listing_payload(org_id))
        lid = create.get_json()['id']
        client.post('/auth/logout')

        client.post('/auth/login', json={'username': 'unpriv', 'password': 'Unpriv123!'})
        resp = client.put(f'/api/listings/{lid}', json={'title': 'Hijacked'})
        assert resp.status_code == 403

    def test_unauthenticated_edit_denied(self, client):
        """Unauthenticated request is rejected."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        create = client.post('/api/listings', json=_listing_payload(org_id))
        lid = create.get_json()['id']
        client.post('/auth/logout')

        resp = client.put(f'/api/listings/{lid}', json={'title': 'Hijacked'})
        assert resp.status_code == 401

    def test_cross_org_create_denied(self, client):
        """mgr_tc1 cannot create a listing under TC2 even with listing.create."""
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        with client.application.app_context():
            org_id = _org_id('TC2')
        resp = client.post('/api/listings', json=_listing_payload(org_id))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Listing status change (POST /status) — org-unit isolation
# ---------------------------------------------------------------------------

class TestListingStatusAuthorization:
    def _create_tc1_listing(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        create = client.post('/api/listings', json=_listing_payload(org_id))
        assert create.status_code == 201
        lid = create.get_json()['id']
        client.post('/auth/logout')
        return lid

    def test_owner_org_can_change_status(self, client):
        """mgr_tc1 can transition their own listing's status."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        resp = client.post(f'/api/listings/{lid}/status',
                           json={'status': 'pending_review'})
        assert resp.status_code == 200

    def test_cross_org_status_change_denied(self, client):
        """mgr_tc2 cannot change the status of a TC1 listing."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.post(f'/api/listings/{lid}/status',
                           json={'status': 'pending_review'})
        assert resp.status_code == 403

    def test_no_permission_status_change_denied(self, client):
        """User without listing.publish cannot change status."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'unpriv', 'password': 'Unpriv123!'})
        resp = client.post(f'/api/listings/{lid}/status',
                           json={'status': 'pending_review'})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Page route — status change (/listings/<id>/status POST form)
# ---------------------------------------------------------------------------

class TestPageRouteStatusAuthorization:
    """The HTML page route must enforce the same permission/org-unit checks
    as the JSON API route — regression tests for the RBAC-bypass finding."""

    def _create_tc1_listing(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        create = client.post('/api/listings', json=_listing_payload(org_id))
        assert create.status_code == 201
        lid = create.get_json()['id']
        client.post('/auth/logout')
        return lid

    def test_owner_org_can_change_status_via_page(self, client):
        """mgr_tc1 can change status via the page (form) route."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        resp = client.post(f'/listings/{lid}/status',
                           data={'status': 'pending_review'})
        # Page route redirects on success.
        assert resp.status_code in (200, 302)

    def test_cross_org_status_change_denied_via_page(self, client):
        """mgr_tc2 (TC2) is denied when trying to mutate a TC1 listing via page route."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.post(f'/listings/{lid}/status',
                           data={'status': 'pending_review'})
        assert resp.status_code == 403

    def test_no_permission_denied_via_page(self, client):
        """User without listing.publish is denied via page route."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'unpriv', 'password': 'Unpriv123!'})
        resp = client.post(f'/listings/{lid}/status',
                           data={'status': 'pending_review'})
        assert resp.status_code == 403

    def test_unauthenticated_denied_via_page(self, client):
        """Unauthenticated POST to page status route is rejected."""
        lid = self._create_tc1_listing(client)
        resp = client.post(f'/listings/{lid}/status',
                           data={'status': 'pending_review'})
        assert resp.status_code in (401, 302)


# ---------------------------------------------------------------------------
# Page route — edit form (/listings/<id>/edit GET)
# ---------------------------------------------------------------------------

class TestPageRouteEditAuthorization:
    """The edit page (GET) must enforce org-unit-scoped listing.edit — same
    class of bug as the status-change route."""

    def _create_tc1_listing(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        create = client.post('/api/listings', json=_listing_payload(org_id))
        assert create.status_code == 201
        lid = create.get_json()['id']
        client.post('/auth/logout')
        return lid

    def test_owner_org_can_open_edit_form(self, client):
        """mgr_tc1 can open the edit form for a TC1 listing."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        resp = client.get(f'/listings/{lid}/edit')
        assert resp.status_code == 200

    def test_cross_org_edit_form_denied(self, client):
        """mgr_tc2 is denied the edit form for a TC1 listing."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.get(f'/listings/{lid}/edit')
        assert resp.status_code == 403

    def test_cross_org_preview_denied(self, client):
        """mgr_tc2 cannot access the preview fragment for a TC1 listing."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.get(f'/listings/{lid}/preview')
        assert resp.status_code == 403

    def test_no_permission_edit_form_denied(self, client):
        """User without listing.edit is denied the edit form."""
        lid = self._create_tc1_listing(client)
        client.post('/auth/login', json={'username': 'unpriv', 'password': 'Unpriv123!'})
        resp = client.get(f'/listings/{lid}/edit')
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Locked / expired listings remain uneditable regardless of auth
# ---------------------------------------------------------------------------

class TestLockedListingProtection:
    def test_cannot_edit_locked_listing(self, client):
        """A user with listing.edit in the right org unit still cannot edit
        a locked listing (status guard in service layer)."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        create = client.post('/api/listings', json=_listing_payload(org_id))
        lid = create.get_json()['id']

        # Advance to locked via allowed transitions: draft→pending_review→published→locked
        client.post(f'/api/listings/{lid}/status', json={'status': 'pending_review'})
        client.post(f'/api/listings/{lid}/status', json={'status': 'published'})
        client.post(f'/api/listings/{lid}/status', json={'status': 'locked'})

        resp = client.put(f'/api/listings/{lid}', json={'title': 'Should Fail'})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Training class routes — role/permission authorization
# ---------------------------------------------------------------------------

class TestClassCreateAuthorization:
    """class.create permission is required for the new-form and POST routes."""

    def test_instructor_can_access_new_form(self, client):
        """Instructor role (has class.create) can open the create form."""
        client.post('/auth/login', json={'username': 'instr_tc1', 'password': 'Instr123!'})
        resp = client.get('/classes/new')
        assert resp.status_code == 200

    def test_property_manager_cannot_access_new_form(self, client):
        """Property manager (no class.create) is denied."""
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        resp = client.get('/classes/new')
        assert resp.status_code == 403

    def test_unprivileged_cannot_access_new_form(self, client):
        """Staff user (no class.create) is denied."""
        client.post('/auth/login', json={'username': 'unpriv', 'password': 'Unpriv123!'})
        resp = client.get('/classes/new')
        assert resp.status_code == 403

    def test_instructor_can_create_class(self, client):
        """Instructor submits the class creation form — succeeds."""
        client.post('/auth/login', json={'username': 'instr_tc1', 'password': 'Instr123!'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        resp = client.post('/classes', data={
            'title': 'Auth Test Class',
            'class_date': '2026-11-15',
            'location': 'Room 200',
            'max_attendees': '20',
            'org_unit_id': str(org_id),
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert '/classes/' in resp.headers.get('Location', '')

    def test_property_manager_cannot_create_class(self, client):
        """Property manager POST to create is denied."""
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        with client.application.app_context():
            org_id = _org_id('TC1')
        resp = client.post('/classes', data={
            'title': 'Unauthorized Class',
            'class_date': '2026-11-15',
            'location': 'Room 200',
            'max_attendees': '20',
            'org_unit_id': str(org_id),
        })
        assert resp.status_code == 403

    def test_instructor_cannot_create_class_in_other_org(self, client):
        """Instructor in TC1 is denied creating a class under TC2."""
        client.post('/auth/login', json={'username': 'instr_tc1', 'password': 'Instr123!'})
        with client.application.app_context():
            org_id = _org_id('TC2')
        resp = client.post('/classes', data={
            'title': 'Cross Org Class',
            'class_date': '2026-11-15',
            'location': 'Room 200',
            'max_attendees': '20',
            'org_unit_id': str(org_id),
        })
        assert resp.status_code == 403

    def test_unauthenticated_create_denied(self, client):
        """Unauthenticated POST is rejected."""
        resp = client.post('/classes', data={
            'title': 'Ghost Class',
            'class_date': '2026-11-15',
            'location': 'Room 200',
            'max_attendees': '20',
            'org_unit_id': '1',
        })
        assert resp.status_code in (401, 302, 403)


class TestClassListDetailAuthorization:
    """Class list/detail enforce org-unit scoping: users can only see
    classes belonging to their accessible org units."""

    def _create_class(self, client, org_code):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        with client.application.app_context():
            org_id = _org_id(org_code)
            from app.models.training import TrainingClass
            tc = TrainingClass(
                title=f'Class in {org_code}',
                instructor_id=User.query.filter_by(username='admin').one().id,
                org_unit_id=org_id,
                class_date=date(2026, 12, 1),
                location='Main Hall',
                max_attendees=50,
            )
            from app.extensions import db as ext_db
            ext_db.session.add(tc)
            ext_db.session.commit()
            class_id = tc.id
        client.post('/auth/logout')
        return class_id

    def test_class_list_requires_auth(self, client):
        """Unauthenticated users are redirected from the class list."""
        resp = client.get('/classes', follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_class_detail_requires_auth(self, client):
        """Unauthenticated users are redirected from class detail."""
        cid = self._create_class(client, 'TC1')
        resp = client.get(f'/classes/{cid}', follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_same_org_user_can_list_classes(self, client):
        """Users see classes in their own org unit."""
        self._create_class(client, 'TC1')
        client.post('/auth/login', json={'username': 'unpriv', 'password': 'Unpriv123!'})
        resp = client.get('/classes')
        assert resp.status_code == 200
        assert b'Class in TC1' in resp.data

    def test_cross_org_user_cannot_see_class_in_list(self, client):
        """Users do NOT see classes from another org unit."""
        self._create_class(client, 'TC1')
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.get('/classes')
        assert resp.status_code == 200
        assert b'Class in TC1' not in resp.data

    def test_same_org_user_can_view_detail(self, client):
        """Users in the same org can view class detail."""
        cid = self._create_class(client, 'TC1')
        client.post('/auth/login', json={'username': 'mgr_tc1', 'password': 'Manager1!'})
        resp = client.get(f'/classes/{cid}')
        assert resp.status_code == 200
        assert b'Class in TC1' in resp.data

    def test_cross_org_user_detail_denied(self, client):
        """Users from another org are denied access to class detail."""
        cid = self._create_class(client, 'TC1')
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.get(f'/classes/{cid}')
        assert resp.status_code == 403

    def test_nonexistent_class_returns_404(self, client):
        """Detail for a non-existent class returns 404, not 500."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/classes/99999')
        assert resp.status_code == 404

    def test_cross_org_user_cannot_register_for_class(self, client):
        """A user outside the class org scope cannot register for the class."""
        cid = self._create_class(client, 'TC1')
        client.post('/auth/login', json={'username': 'mgr_tc2', 'password': 'Manager2!'})
        resp = client.post(f'/classes/{cid}/register', follow_redirects=False)
        assert resp.status_code == 403

    def test_zero_org_membership_user_cannot_register_for_class(self, client):
        """A user with no org memberships must be denied class registration."""
        from app.models.user import User
        from app.models.user import Role
        from app.extensions import db as ext_db

        cid = self._create_class(client, 'TC1')
        with client.application.app_context():
            user = User(username='noorg', email='noorg@test.com', full_name='No Org')
            user.set_password('Noorg123!')
            user.roles.append(Role.query.filter_by(name='staff').one())
            ext_db.session.add(user)
            ext_db.session.commit()
        client.post('/auth/login', json={'username': 'noorg', 'password': 'Noorg123!'})
        resp = client.post(f'/classes/{cid}/register', follow_redirects=False)
        assert resp.status_code == 403
