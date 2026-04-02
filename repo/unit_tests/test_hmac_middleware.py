"""Tests for the HMAC request-signing middleware (verify_hmac_signature).

A minimal Flask app is constructed with TESTING=False so the decorator's
early-exit bypass is inactive and all validation branches are exercised.
"""
import hashlib
import hmac as _hmac
import time
import uuid

import pytest
from flask import Flask, jsonify

from app.extensions import db as _db
from app.api.middleware import verify_hmac_signature

SECRET = 'test-hmac-secret'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='function')
def hmac_app():
    """Minimal Flask app with one HMAC-protected endpoint."""
    app = Flask(__name__)
    app.config.update({
        'TESTING': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret',
        'HMAC_SECRET': SECRET,
        'HMAC_WINDOW_SECONDS': 300,
        'WTF_CSRF_ENABLED': False,
    })
    _db.init_app(app)

    @app.route('/ping', methods=['POST'])
    @verify_hmac_signature
    def ping():
        return jsonify({'ok': True}), 200

    with app.app_context():
        from app.models.nonce import HmacNonce  # ensure table is registered
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(hmac_app):
    return hmac_app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sign(method, path, body=b'', secret=SECRET, timestamp=None, nonce=None):
    """Return a dict of the three HMAC request headers for the given request."""
    ts = timestamp if timestamp is not None else int(time.time())
    n = nonce or str(uuid.uuid4())
    body_sha = hashlib.sha256(body).hexdigest()
    msg = f"{method}\n{path}\n{ts}\n{n}\n{body_sha}".encode()
    sig = _hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return {'X-Signature': sig, 'X-Timestamp': str(ts), 'X-Nonce': n}


# ---------------------------------------------------------------------------
# Header validation
# ---------------------------------------------------------------------------

class TestMissingHeaders:
    def test_no_headers(self, client):
        resp = client.post('/ping')
        assert resp.status_code == 401
        assert 'Missing' in resp.get_json()['error']

    def test_missing_signature(self, client):
        resp = client.post('/ping', headers={
            'X-Timestamp': str(int(time.time())),
            'X-Nonce': str(uuid.uuid4()),
        })
        assert resp.status_code == 401

    def test_missing_timestamp(self, client):
        resp = client.post('/ping', headers={
            'X-Signature': 'abc',
            'X-Nonce': str(uuid.uuid4()),
        })
        assert resp.status_code == 401

    def test_missing_nonce(self, client):
        resp = client.post('/ping', headers={
            'X-Signature': 'abc',
            'X-Timestamp': str(int(time.time())),
        })
        assert resp.status_code == 401

    def test_non_integer_timestamp(self, client):
        resp = client.post('/ping', headers={
            'X-Signature': 'abc',
            'X-Timestamp': 'not-a-number',
            'X-Nonce': str(uuid.uuid4()),
        })
        assert resp.status_code == 401
        assert 'Invalid X-Timestamp' in resp.get_json()['error']


# ---------------------------------------------------------------------------
# Timestamp window
# ---------------------------------------------------------------------------

class TestTimestampWindow:
    def test_expired_timestamp_rejected(self, client):
        old_ts = int(time.time()) - 301  # just outside 5-minute window
        headers = _sign('POST', '/ping', timestamp=old_ts)
        resp = client.post('/ping', headers=headers)
        assert resp.status_code == 401
        assert 'window' in resp.get_json()['error']

    def test_future_timestamp_rejected(self, client):
        future_ts = int(time.time()) + 301
        headers = _sign('POST', '/ping', timestamp=future_ts)
        resp = client.post('/ping', headers=headers)
        assert resp.status_code == 401

    def test_timestamp_at_boundary_accepted(self, client):
        ts = int(time.time()) - 299  # just inside the window
        headers = _sign('POST', '/ping', timestamp=ts)
        resp = client.post('/ping', headers=headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Signature correctness
# ---------------------------------------------------------------------------

class TestSignatureVerification:
    def test_valid_request_accepted(self, client):
        headers = _sign('POST', '/ping')
        resp = client.post('/ping', headers=headers)
        assert resp.status_code == 200
        assert resp.get_json() == {'ok': True}

    def test_wrong_secret_rejected(self, client):
        headers = _sign('POST', '/ping', secret='wrong-secret')
        resp = client.post('/ping', headers=headers)
        assert resp.status_code == 401
        assert 'Invalid signature' in resp.get_json()['error']

    def test_body_included_in_signature(self, client):
        body = b'{"key": "value"}'
        # Sign without body, then send with body — signature should mismatch.
        headers = _sign('POST', '/ping', body=b'')
        resp = client.post('/ping', data=body, headers=headers)
        assert resp.status_code == 401

    def test_path_included_in_signature(self, client):
        # Sign for /other, send to /ping — should fail.
        headers = _sign('POST', '/other')
        resp = client.post('/ping', headers=headers)
        assert resp.status_code == 401

    def test_method_included_in_signature(self, client):
        # Sign as GET, send as POST — should fail.
        headers = _sign('GET', '/ping')
        resp = client.post('/ping', headers=headers)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Replay detection
# ---------------------------------------------------------------------------

class TestReplayDetection:
    def test_duplicate_nonce_rejected(self, client):
        nonce = str(uuid.uuid4())
        headers = _sign('POST', '/ping', nonce=nonce)
        first = client.post('/ping', headers=headers)
        assert first.status_code == 200

        # Replay: same nonce, same timestamp, same everything.
        second = client.post('/ping', headers=headers)
        assert second.status_code == 401
        assert 'replay' in second.get_json()['error'].lower()

    def test_different_nonces_both_accepted(self, client):
        h1 = _sign('POST', '/ping', nonce=str(uuid.uuid4()))
        h2 = _sign('POST', '/ping', nonce=str(uuid.uuid4()))
        assert client.post('/ping', headers=h1).status_code == 200
        assert client.post('/ping', headers=h2).status_code == 200


# ---------------------------------------------------------------------------
# HX-Request header must NOT bypass HMAC
# ---------------------------------------------------------------------------

class TestHxRequestDoesNotBypass:
    """Regression: setting the HX-Request header must not skip HMAC checks."""

    def test_hx_request_header_alone_is_rejected(self, client):
        resp = client.post('/ping', headers={'HX-Request': 'true'})
        assert resp.status_code == 401

    def test_hx_request_with_invalid_signature_is_rejected(self, client):
        headers = {'HX-Request': 'true', 'X-Signature': 'bad', 'X-Timestamp': str(int(time.time())), 'X-Nonce': str(uuid.uuid4())}
        resp = client.post('/ping', headers=headers)
        assert resp.status_code == 401
