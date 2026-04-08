import pytest

VALID_PW = 'Secret1!'


class TestRegister:
    def test_register_success(self, client):
        resp = client.post('/auth/register', json={
            'username': 'newuser',
            'password': VALID_PW,
            'email': 'newuser@test.com',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['username'] == 'newuser'

    def test_register_duplicate_username(self, client):
        client.post('/auth/register', json={'username': 'dup', 'password': VALID_PW})
        resp = client.post('/auth/register', json={'username': 'dup', 'password': VALID_PW})
        assert resp.status_code == 409

    def test_register_missing_username(self, client):
        resp = client.post('/auth/register', json={'password': VALID_PW})
        assert resp.status_code == 400

    def test_register_weak_password(self, client):
        resp = client.post('/auth/register', json={'username': 'weakpw', 'password': 'weak'})
        assert resp.status_code == 400

    def test_register_cannot_self_assign_org_unit(self, client):
        resp = client.post('/auth/register', json={
            'username': 'orgassign',
            'password': VALID_PW,
            'org_unit_id': 1,
        })
        assert resp.status_code == 400
        assert 'organization' in resp.get_json()['error'].lower()


class TestLogin:
    def test_login_success(self, client):
        client.post('/auth/register', json={'username': 'logintest', 'password': VALID_PW})
        resp = client.post('/auth/login', json={'username': 'logintest', 'password': VALID_PW})
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        client.post('/auth/register', json={'username': 'wrongpw', 'password': VALID_PW})
        resp = client.post('/auth/login', json={'username': 'wrongpw', 'password': 'wrong'})
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = client.post('/auth/login', json={'username': 'nobody', 'password': 'pass'})
        assert resp.status_code == 401


class TestMe:
    def test_me_unauthenticated(self, client):
        resp = client.get('/auth/me')
        assert resp.status_code == 401

    def test_me_authenticated(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/auth/me')
        assert resp.status_code == 200
        assert resp.get_json()['username'] == 'admin'


class TestLogout:
    def test_logout(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/auth/logout')
        assert resp.status_code == 200
        resp2 = client.get('/auth/me')
        assert resp2.status_code == 401

    def test_logout_sets_no_store_cache_header(self, client):
        """Logout response must carry Cache-Control: no-store to prevent browser caching."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/auth/logout')
        assert 'no-store' in resp.headers.get('Cache-Control', '')

    def test_logout_sets_clear_site_data_header(self, client):
        """Logout must send Clear-Site-Data to purge browser HTTP caches."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/auth/logout')
        csd = resp.headers.get('Clear-Site-Data', '')
        assert '"cache"' in csd

    def test_logout_htmx_triggers_sw_cache_clear(self, client):
        """HTMX logout must include HX-Trigger: clearSwCache."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/auth/logout', headers={'HX-Request': 'true'})
        assert resp.headers.get('HX-Trigger') == 'clearSwCache'

    def test_logout_non_htmx_omits_hx_trigger(self, client):
        """Non-HTMX logout must not include HX-Trigger."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.post('/auth/logout')
        assert resp.headers.get('HX-Trigger') is None


class TestNavSmoke:
    """Smoke tests: every link in the main nav must resolve (not 404)."""

    def test_login_page_reachable(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200

    def test_listings_nav_reachable(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/listings')
        assert resp.status_code == 200

    def test_drugs_nav_reachable(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/drugs')
        assert resp.status_code == 200

    def test_training_nav_reachable(self, client):
        """Nav link /classes must resolve — previously the template linked to /training (404)."""
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/classes')
        assert resp.status_code == 200

    def test_admin_nav_reachable(self, client):
        client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        resp = client.get('/admin')
        assert resp.status_code == 200
