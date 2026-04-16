import pytest


class TestAdminAPI:
    def _create_tc2_admin(self, client):
        from app.models.user import User, Role
        from app.models.organization import OrgUnit, UserOrgUnit
        from app.utils.constants import OrgUnitLevel
        from app.extensions import db as _db

        with client.application.app_context():
            org = OrgUnit.query.filter_by(code='TC2').first()
            if not org:
                org = OrgUnit(name='Other Campus', code='TC2', level=OrgUnitLevel.CAMPUS.value)
                _db.session.add(org)
                _db.session.flush()
            admin = User.query.filter_by(username='admin_tc2').first()
            if not admin:
                admin = User(username='admin_tc2', email='admin_tc2@test.com', full_name='Scoped Admin')
                admin.set_password('Scoped123!')
                _db.session.add(admin)
                _db.session.flush()
                admin.roles.append(Role.query.filter_by(name='org_admin').first())
                _db.session.add(UserOrgUnit(user_id=admin.id, org_unit_id=org.id, is_primary=True))
                _db.session.commit()
            return admin, org

    def test_list_users_requires_auth(self, client):
        resp = client.get('/api/admin/users')
        assert resp.status_code == 401

    def test_list_users_as_admin(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/api/admin/users')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_users_as_staff_forbidden(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get('/api/admin/users')
        assert resp.status_code == 403

    def test_list_org_units(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/api/admin/org-units')
        assert resp.status_code == 200
        data = resp.get_json()
        assert any(u['code'] == 'TC1' for u in data)

    def test_audit_logs(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/api/admin/audit-logs')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_assign_role(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        # Get staff user id
        users = client.get('/api/admin/users').get_json()
        staff = next(u for u in users if u['username'] == 'staffuser')
        resp = client.post(f'/api/admin/users/{staff["id"]}/roles', json={'role': 'instructor'})
        assert resp.status_code == 200
        assert 'instructor' in resp.get_json()['roles']

    def test_temp_grant(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        users = client.get('/api/admin/users').get_json()
        staff = next(u for u in users if u['username'] == 'staffuser')
        resp = client.post(f'/api/admin/users/{staff["id"]}/temp-grants', json={
            'permission': 'drug.approve',
            'hours': 24,
            'reason': 'Emergency coverage',
        })
        assert resp.status_code == 201
        assert resp.get_json()['is_active'] is True

    def test_admin_user_list_scoped_to_org(self, client):
        self._create_tc2_admin(client)
        client.post('/auth/login', json={'username': 'admin_tc2', 'password': 'Scoped123!'})
        resp = client.get('/api/admin/users')
        assert resp.status_code == 200
        usernames = {u['username'] for u in resp.get_json()}
        assert 'admin' not in usernames
        assert 'staffuser' not in usernames

    def test_out_of_scope_user_role_assign_denied(self, client):
        self._create_tc2_admin(client)
        client.post('/auth/login', json={'username': 'admin_tc2', 'password': 'Scoped123!'})
        # TC2 admin should not even see TC1 users, but direct object path must also deny.
        with client.application.app_context():
            from app.models.user import User
            target = User.query.filter_by(username='staffuser').first()
            target_id = target.id
        resp = client.post(f'/api/admin/users/{target_id}/roles', json={'role': 'instructor'})
        assert resp.status_code == 403

    def test_temp_grant_invalid_hours(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        users = client.get('/api/admin/users').get_json()
        staff = next(u for u in users if u['username'] == 'staffuser')
        resp = client.post(f'/api/admin/users/{staff["id"]}/temp-grants', json={
            'permission': 'drug.approve',
            'hours': 0,
            'reason': 'Invalid window',
        })
        assert resp.status_code == 400

    def test_scoped_admin_audit_logs_filtered(self, client):
        self._create_tc2_admin(client)
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        client.get('/api/admin/users')
        client.post('/auth/logout')
        client.post('/auth/login', json={'username': 'admin_tc2', 'password': 'Scoped123!'})
        resp = client.get('/api/admin/audit-logs')
        assert resp.status_code == 200
        actions = {entry['action'] for entry in resp.get_json()}
        assert 'user.register' not in actions

    def test_scoped_admin_permission_audit_filtered(self, client):
        self._create_tc2_admin(client)
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        users = client.get('/api/admin/users').get_json()
        staff = next(u for u in users if u['username'] == 'staffuser')
        client.post(f'/api/admin/users/{staff["id"]}/temp-grants', json={
            'permission': 'drug.approve',
            'hours': 1,
            'reason': 'TC1 grant',
        })
        client.post('/auth/logout')
        client.post('/auth/login', json={'username': 'admin_tc2', 'password': 'Scoped123!'})
        resp = client.get('/api/admin/permissions/audit')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_scoped_admin_cannot_revoke_out_of_scope_temp_grant(self, client):
        self._create_tc2_admin(client)
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        users = client.get('/api/admin/users').get_json()
        staff = next(u for u in users if u['username'] == 'staffuser')
        grant_resp = client.post(f'/api/admin/users/{staff["id"]}/temp-grants', json={
            'permission': 'drug.approve',
            'hours': 1,
            'reason': 'Scoped revoke deny',
        })
        grant_id = grant_resp.get_json()['id']
        client.post('/auth/logout')
        client.post('/auth/login', json={'username': 'admin_tc2', 'password': 'Scoped123!'})
        resp = client.post(f'/api/admin/temp-grants/{grant_id}/revoke')
        assert resp.status_code == 403


class TestOrgSettings:
    def _org_id(self, client):
        orgs = client.get('/api/admin/org-units').get_json()
        return next(o['id'] for o in orgs if o['code'] == 'TC1')

    def test_get_org_settings(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        org_id = self._org_id(client)
        resp = client.get(f'/api/admin/org-units/{org_id}/settings')
        assert resp.status_code == 200
        assert resp.get_json()['reviewer_display_mode'] in ('anonymous', 'initials', 'full_name')

    def test_update_org_settings_valid(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        org_id = self._org_id(client)
        resp = client.patch(f'/api/admin/org-units/{org_id}/settings',
                            json={'reviewer_display_mode': 'initials'})
        assert resp.status_code == 200
        assert resp.get_json()['reviewer_display_mode'] == 'initials'

    def test_update_org_settings_persists(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        org_id = self._org_id(client)
        client.patch(f'/api/admin/org-units/{org_id}/settings',
                     json={'reviewer_display_mode': 'full_name'})
        resp = client.get(f'/api/admin/org-units/{org_id}/settings')
        assert resp.get_json()['reviewer_display_mode'] == 'full_name'

    def test_update_org_settings_invalid_mode(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        org_id = self._org_id(client)
        resp = client.patch(f'/api/admin/org-units/{org_id}/settings',
                            json={'reviewer_display_mode': 'banana'})
        assert resp.status_code == 400

    def test_update_org_settings_requires_permission(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.patch('/api/admin/org-units/1/settings',
                            json={'reviewer_display_mode': 'full_name'})
        assert resp.status_code == 403

    def test_org_settings_reflected_in_list_orgs(self, client):
        """reviewer_display_mode must appear in the org-units list response."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        org_id = self._org_id(client)
        client.patch(f'/api/admin/org-units/{org_id}/settings',
                     json={'reviewer_display_mode': 'initials'})
        orgs = client.get('/api/admin/org-units').get_json()
        org = next(o for o in orgs if o['id'] == org_id)
        assert org['reviewer_display_mode'] == 'initials'

    def test_admin_org_settings_page_reachable(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/admin/org-settings')
        assert resp.status_code == 200

    def test_admin_org_settings_page_form_submit(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        org_id = self._org_id(client)
        resp = client.post(f'/admin/org-settings/{org_id}',
                           data={'reviewer_display_mode': 'full_name'},
                           follow_redirects=True)
        assert resp.status_code == 200
        # Verify the change stuck
        settings = client.get(f'/api/admin/org-units/{org_id}/settings').get_json()
        assert settings['reviewer_display_mode'] == 'full_name'

    def test_admin_org_settings_page_non_admin_forbidden(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get('/admin/org-settings')
        assert resp.status_code == 403

    def test_scoped_admin_cannot_update_out_of_scope_org(self, client):
        from app.models.user import User, Role
        from app.models.organization import OrgUnit, UserOrgUnit
        from app.utils.constants import OrgUnitLevel
        from app.extensions import db as _db

        with client.application.app_context():
            tc2 = OrgUnit(name='Other Campus', code='TC2', level=OrgUnitLevel.CAMPUS.value)
            _db.session.add(tc2)
            _db.session.flush()
            tc1 = OrgUnit.query.filter_by(code='TC1').first()
            scoped = User(username='scoped_org_admin', email='scoped_org_admin@test.com', full_name='Scoped Admin')
            scoped.set_password('Scoped123!')
            _db.session.add(scoped)
            _db.session.flush()
            scoped.roles.append(Role.query.filter_by(name='org_admin').first())
            _db.session.add(UserOrgUnit(user_id=scoped.id, org_unit_id=tc2.id, is_primary=True))
            _db.session.commit()
            tc1_id = tc1.id

        client.post('/auth/login', json={'username': 'scoped_org_admin', 'password': 'Scoped123!'})
        resp = client.patch(f'/api/admin/org-units/{tc1_id}/settings',
                            json={'reviewer_display_mode': 'full_name'})
        assert resp.status_code == 403


class TestBackupRestore:
    def test_restore_requires_filename(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/admin/backups/restore', json={})
        assert resp.status_code == 400
        assert 'filename' in resp.get_json()['error']

    def test_restore_nonexistent_file(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/admin/backups/restore',
                           json={'filename': 'does_not_exist.db.enc'})
        assert resp.status_code == 404

    def test_restore_requires_admin_permission(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.post('/api/admin/backups/restore',
                           json={'filename': 'backup.db.enc'})
        assert resp.status_code == 403

    def test_restore_rejects_non_enc_file(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/admin/backups/restore',
                           json={'filename': 'backup.db'})
        assert resp.status_code == 400
        assert '.enc' in resp.get_json()['error']


class TestAdminMissingRoutes:
    """Tests for admin API routes not covered elsewhere."""

    def test_get_user_by_id(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        users = client.get('/api/admin/users').get_json()
        staff = next(u for u in users if u['username'] == 'staffuser')
        resp = client.get(f'/api/admin/users/{staff["id"]}')
        assert resp.status_code == 200
        assert resp.get_json()['username'] == 'staffuser'

    def test_get_user_by_id_out_of_scope_denied(self, client):
        from app.models.user import User, Role
        from app.models.organization import OrgUnit, UserOrgUnit
        from app.utils.constants import OrgUnitLevel
        from app.extensions import db as _db

        with client.application.app_context():
            org2 = OrgUnit(name='Other Campus', code='TC_OOS', level=OrgUnitLevel.CAMPUS.value)
            _db.session.add(org2)
            _db.session.flush()
            scoped = User(username='scoped_admin2', email='scoped2@test.com', full_name='Scoped 2')
            scoped.set_password('Scoped123!')
            _db.session.add(scoped)
            _db.session.flush()
            scoped.roles.append(Role.query.filter_by(name='org_admin').first())
            _db.session.add(UserOrgUnit(user_id=scoped.id, org_unit_id=org2.id, is_primary=True))
            _db.session.commit()
            target_id = User.query.filter_by(username='staffuser').first().id

        client.post('/auth/login', json={'username': 'scoped_admin2', 'password': 'Scoped123!'})
        resp = client.get(f'/api/admin/users/{target_id}')
        assert resp.status_code == 403

    def test_delete_role(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        users = client.get('/api/admin/users').get_json()
        staff = next(u for u in users if u['username'] == 'staffuser')
        client.post(f'/api/admin/users/{staff["id"]}/roles', json={'role': 'instructor'})
        resp = client.delete(f'/api/admin/users/{staff["id"]}/roles/instructor')
        assert resp.status_code == 200
        assert 'instructor' not in resp.get_json()['roles']

    def test_delete_role_out_of_scope_denied(self, client):
        from app.models.user import User, Role
        from app.models.organization import OrgUnit, UserOrgUnit
        from app.utils.constants import OrgUnitLevel
        from app.extensions import db as _db

        with client.application.app_context():
            org2 = OrgUnit(name='Other Campus', code='TC_DEL', level=OrgUnitLevel.CAMPUS.value)
            _db.session.add(org2)
            _db.session.flush()
            scoped = User(username='scoped_del', email='scoped_del@test.com', full_name='Scoped Del')
            scoped.set_password('Scoped123!')
            _db.session.add(scoped)
            _db.session.flush()
            scoped.roles.append(Role.query.filter_by(name='org_admin').first())
            _db.session.add(UserOrgUnit(user_id=scoped.id, org_unit_id=org2.id, is_primary=True))
            _db.session.commit()
            target_id = User.query.filter_by(username='staffuser').first().id

        client.post('/auth/login', json={'username': 'scoped_del', 'password': 'Scoped123!'})
        resp = client.delete(f'/api/admin/users/{target_id}/roles/staff')
        assert resp.status_code == 403

    def test_create_org_unit(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/api/admin/org-units', json={
            'name': 'New Department',
            'code': 'ND1',
            'level': 'department',
        })
        assert resp.status_code == 201
        assert resp.get_json()['code'] == 'ND1'

    def test_create_org_unit_requires_permission(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.post('/api/admin/org-units', json={
            'name': 'Unauthorized Dept',
            'code': 'UD1',
            'level': 'department',
        })
        assert resp.status_code == 403

    def test_list_backups_api(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/api/admin/backups')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_backups_api_requires_permission(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get('/api/admin/backups')
        assert resp.status_code == 403

    def test_run_backup_api_requires_permission(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.post('/api/admin/backup')
        assert resp.status_code == 403


class TestBackupAdminPages:
    def test_backups_page_reachable_for_admin(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/admin/backups')
        assert resp.status_code == 200
        assert b'Backups' in resp.data

    def test_backups_page_forbidden_for_staff(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get('/admin/backups')
        assert resp.status_code == 403

    def test_admin_backups_page_reachable(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/admin/backups')
        assert resp.status_code == 200
        assert b'Backups' in resp.data

    def test_admin_backups_page_non_admin_forbidden(self, client):
        client.post('/auth/login', json={'username': 'staffuser', 'password': 'staffpass'})
        resp = client.get('/admin/backups')
        assert resp.status_code == 403
