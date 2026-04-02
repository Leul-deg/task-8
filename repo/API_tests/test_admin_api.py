import pytest


class TestAdminAPI:
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
