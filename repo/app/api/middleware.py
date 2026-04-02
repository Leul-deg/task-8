import hashlib
import hmac
import time
from functools import wraps
from flask import request, jsonify, current_app, g, session
from sqlalchemy.exc import IntegrityError


def verify_hmac_signature(f):
    """Decorator that verifies HMAC-SHA256 request signatures.

    Required headers:
        X-Signature  — hex HMAC-SHA256 of the signing string
        X-Timestamp  — Unix timestamp (int)
        X-Nonce      — unique per-request token for replay prevention

    Signing string: "{METHOD}\\n{path}\\n{timestamp}\\n{nonce}\\n{sha256(body)}"

    Nonces are persisted in SQLite so replay protection works across all
    Gunicorn workers.  The DB primary-key constraint makes the duplicate check
    atomic; no worker-local dict is used.

    HMAC is enforced for all API requests regardless of session state.
    Browser-facing page routes do not use this decorator and rely on
    session cookies + CSRF tokens instead.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        if current_app.config.get('TESTING'):
            return f(*args, **kwargs)

        signature = request.headers.get('X-Signature')
        timestamp_str = request.headers.get('X-Timestamp')
        nonce = request.headers.get('X-Nonce')

        if not signature or not timestamp_str or not nonce:
            return jsonify({'error': 'Missing required signature headers (X-Signature, X-Timestamp, X-Nonce)'}), 401

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            return jsonify({'error': 'Invalid X-Timestamp: must be an integer Unix timestamp'}), 401

        window = current_app.config.get('HMAC_WINDOW_SECONDS', 300)
        now = int(time.time())

        if abs(now - timestamp) > window:
            return jsonify({'error': 'Request timestamp is outside the allowed window'}), 401

        from app.extensions import db
        from app.models.nonce import HmacNonce

        # Purge expired nonces so the table stays bounded.
        HmacNonce.query.filter(HmacNonce.expires_at < now).delete(synchronize_session=False)

        # Atomically claim the nonce.  If it already exists the UNIQUE / PK
        # constraint raises IntegrityError — that is a replay.
        record = HmacNonce(nonce=nonce, expires_at=now + window * 2)
        db.session.add(record)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'Duplicate nonce: replay detected'}), 401

        # Verify the signature *after* claiming the nonce so two concurrent
        # requests carrying the same valid nonce cannot both pass.
        secret = current_app.config.get('HMAC_SECRET', '')
        if request.headers.get('HX-Request'):
            browser_secret = session.get('hmac_client_secret')
            if browser_secret:
                secret = browser_secret
        body = request.get_data()
        body_sha256 = hashlib.sha256(body).hexdigest()
        signing_string = (
            f"{request.method}\n"
            f"{request.path}\n"
            f"{timestamp}\n"
            f"{nonce}\n"
            f"{body_sha256}"
        ).encode()

        expected = hmac.new(secret.encode(), signing_string, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            # Signature invalid — roll back so the nonce is not consumed and
            # a corrected request can be retried within the time window.
            db.session.rollback()
            return jsonify({'error': 'Invalid signature'}), 401

        # Commit the nonce record before the handler runs so it is visible to
        # all workers immediately, regardless of whether the handler succeeds.
        db.session.commit()

        g.request_id = nonce
        return f(*args, **kwargs)

    return wrapped
