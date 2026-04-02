from app.extensions import db


class HmacNonce(db.Model):
    """Persisted nonce store for HMAC replay protection.

    Shared across all Gunicorn workers via SQLite (WAL mode).
    The primary-key uniqueness constraint makes duplicate-nonce detection atomic.
    """
    __tablename__ = 'hmac_nonce'

    nonce = db.Column(db.String(256), primary_key=True)
    expires_at = db.Column(db.Integer, nullable=False, index=True)
