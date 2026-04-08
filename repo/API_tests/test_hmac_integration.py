"""Integration tests: HMAC enforcement on real API routes.

These tests create a non-TESTING app so the HMAC middleware is fully active,
proving that:
  - HX-Request headers alone cannot bypass signature verification
  - Replay detection works on actual API endpoints
  - Invalid/missing signatures are rejected on real routes
"""
import base64
import hashlib
import hmac as _hmac
import os
import time
import uuid

import pytest
from flask import Flask

from app import create_app
from app.extensions import db as _db
from app.models.user import User, Role, Permission
from app.models.organization import OrgUnit, UserOrgUnit
from app.utils.constants import OrgUnitLevel, DEFAULT_PERMISSIONS, DEFAULT_ROLES

HMAC_SECRET = 'integration-test-hmac-secret'
ENCRYPTION_KEY = base64.b64encode(os.urandom(32)).decode()

REAL_API_ROUTES = [
    ('GET', '/api/drugs'),
    ('POST', '/api/drugs'),
    ('GET', '/api/listings'),
]


@pytest.fixture(scope='function')
def live_app():
    """Full app with TESTING=False so HMAC middleware is active."""
    app = create_app('testing')
    app.config['TESTING'] = False
    app.config['HMAC_SECRET'] = HMAC_SECRET
    app.config['HMAC_WINDOW_SECONDS'] = 300
    app.config['ENCRYPTION_KEY'] = ENCRYPTION_KEY
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['LOGIN_MAX_ATTEMPTS_PER_IP'] = 0
    app.config['LOGIN_MAX_ATTEMPTS_PER_USERNAME'] = 0

    with app.app_context():
        _db.create_all()
        _seed(app)
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(live_app):
    return live_app.test_client()


def _seed(app):
    perms = {}
    for pdata in DEFAULT_PERMISSIONS:
        p = Permission(**pdata)
        _db.session.add(p)
        perms[pdata['codename']] = p
    _db.session.flush()

    roles = {}
    for rdata in DEFAULT_ROLES:
        r = Role(**rdata)
        _db.session.add(r)
        roles[rdata['name']] = r
    _db.session.flush()

    for p in perms.values():
        roles['org_admin'].permissions.append(p)

    org = OrgUnit(name='Test Campus', code='TC1', level=OrgUnitLevel.CAMPUS.value)
    _db.session.add(org)
    _db.session.flush()

    admin = User(username='admin', email='admin@test.com', full_name='Admin User')
    admin.set_password('admin123')
    _db.session.add(admin)
    _db.session.flush()
    admin.roles.append(roles['org_admin'])
    _db.session.add(UserOrgUnit(user_id=admin.id, org_unit_id=org.id, is_primary=True))
    _db.session.commit()


def _sign(method, path, body=b'', secret=HMAC_SECRET, timestamp=None, nonce=None):
    ts = timestamp if timestamp is not None else int(time.time())
    n = nonce or str(uuid.uuid4())
    body_sha = hashlib.sha256(body).hexdigest()
    msg = f"{method}\n{path}\n{ts}\n{n}\n{body_sha}".encode()
    sig = _hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return {'X-Signature': sig, 'X-Timestamp': str(ts), 'X-Nonce': n}


# ---------------------------------------------------------------------------
# HX-Request must NOT bypass HMAC on real routes
# ---------------------------------------------------------------------------

class TestHxRequestBypassOnRealRoutes:
    """HX-Request header alone must not skip HMAC on any real API route."""

    @pytest.mark.parametrize('method,path', REAL_API_ROUTES)
    def test_hx_request_alone_rejected(self, client, method, path):
        resp = getattr(client, method.lower())(path, headers={'HX-Request': 'true'})
        assert resp.status_code == 401
        assert 'Missing' in resp.get_json().get('error', '')

    @pytest.mark.parametrize('method,path', REAL_API_ROUTES)
    def test_hx_request_with_bad_signature_rejected(self, client, method, path):
        headers = {
            'HX-Request': 'true',
            'X-Signature': 'deadbeef',
            'X-Timestamp': str(int(time.time())),
            'X-Nonce': str(uuid.uuid4()),
        }
        resp = getattr(client, method.lower())(path, headers=headers)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Replay detection on real routes
# ---------------------------------------------------------------------------

class TestReplayOnRealRoutes:
    def test_duplicate_nonce_rejected_on_drugs_endpoint(self, client):
        nonce = str(uuid.uuid4())
        headers = _sign('GET', '/api/drugs', nonce=nonce)

        first = client.get('/api/drugs', headers=headers)
        # First request passes HMAC but may fail at login_required — either
        # 200 (if session exists) or 401 (login_required). What matters is
        # the *second* call is rejected specifically for replay.
        assert first.status_code in (200, 401)

        second = client.get('/api/drugs', headers=headers)
        assert second.status_code == 401
        assert 'replay' in second.get_json().get('error', '').lower()


# ---------------------------------------------------------------------------
# Signature verification on real routes
# ---------------------------------------------------------------------------

class TestSignatureOnRealRoutes:
    def test_wrong_secret_rejected(self, client):
        headers = _sign('GET', '/api/drugs', secret='wrong-secret')
        resp = client.get('/api/drugs', headers=headers)
        assert resp.status_code == 401
        assert 'Invalid signature' in resp.get_json().get('error', '')

    def test_expired_timestamp_rejected(self, client):
        old_ts = int(time.time()) - 301
        headers = _sign('GET', '/api/drugs', timestamp=old_ts)
        resp = client.get('/api/drugs', headers=headers)
        assert resp.status_code == 401
        assert 'window' in resp.get_json().get('error', '')

    def test_valid_hmac_passes_middleware(self, client):
        """Valid HMAC should pass the middleware layer (may still need login)."""
        headers = _sign('GET', '/api/drugs')
        resp = client.get('/api/drugs', headers=headers)
        # 401 from login_required (not HMAC) or 200 — both prove HMAC passed
        if resp.status_code == 401:
            assert 'signature' not in resp.get_json().get('error', '').lower()
            assert 'Missing' not in resp.get_json().get('error', '')


# ---------------------------------------------------------------------------
# Session-authenticated requests must still require HMAC on API routes
# ---------------------------------------------------------------------------

class TestSessionDoesNotBypassHmac:
    def _login(self, client):
        client.post('/auth/login', data={
            'username': 'admin', 'password': 'admin123',
        }, content_type='application/x-www-form-urlencoded')

    def test_logged_in_user_without_hmac_rejected(self, client):
        """Authenticated session alone must not bypass HMAC on API routes."""
        self._login(client)
        resp = client.get('/api/drugs')
        assert resp.status_code == 401
        assert 'Missing' in resp.get_json().get('error', '')

    def test_logged_in_listings_api_without_hmac_rejected(self, client):
        """Runtime regression guard for the specific /api/listings bypass path."""
        self._login(client)
        resp = client.get('/api/listings?per_page=5')
        assert resp.status_code == 401
        assert 'Missing' in resp.get_json().get('error', '')

    def test_logged_in_htmx_without_hmac_rejected(self, client):
        """Session + HX-Request without HMAC is still rejected on API routes."""
        self._login(client)
        resp = client.get('/api/drugs', headers={'HX-Request': 'true'})
        assert resp.status_code == 401

    def test_logged_in_user_with_valid_hmac_succeeds(self, client):
        """Authenticated session with valid HMAC passes both layers."""
        self._login(client)
        headers = _sign('GET', '/api/drugs')
        resp = client.get('/api/drugs', headers=headers)
        assert resp.status_code == 200

    def test_unauthenticated_with_valid_hmac_needs_login(self, client):
        """Valid HMAC alone passes middleware but login_required still blocks."""
        headers = _sign('GET', '/api/drugs')
        resp = client.get('/api/drugs', headers=headers)
        assert resp.status_code == 401
        error = resp.get_json().get('error', '')
        assert 'signature' not in error.lower()
        assert 'Missing' not in error


class TestBrowserHtmxPageRoutes:
    """HTMX browser traffic should use page routes, not signed API endpoints."""

    def test_logged_in_hx_listings_page_works_without_hmac(self, client):
        client.post('/auth/login', data={
            'username': 'admin', 'password': 'admin123',
        }, content_type='application/x-www-form-urlencoded')
        resp = client.get('/listings?per_page=5', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        assert b'listing-card' in resp.data or b'No listings found' in resp.data


class TestJsonAuthEndpointsRequireHmac:
    def test_json_login_without_hmac_rejected(self, client):
        resp = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
        assert resp.status_code == 401
        assert 'Missing' in resp.get_json().get('error', '')

    def test_json_login_with_valid_hmac_succeeds(self, client):
        body = b'{"username":"admin","password":"admin123"}'
        headers = _sign('POST', '/auth/login', body=body)
        resp = client.post('/auth/login', data=body, headers=headers, content_type='application/json')
        assert resp.status_code == 200
