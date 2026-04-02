import base64
import hashlib
import hmac
import os
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _load_key(key_b64: str) -> bytes:
    """Decode a base64-encoded 32-byte AES key."""
    return base64.b64decode(key_b64)


def encrypt(plaintext: str, key_b64: str) -> str:
    """AES-GCM encrypt plaintext. Returns base64(nonce + ciphertext)."""
    key = _load_key(key_b64)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(token: str, key_b64: str) -> str:
    """AES-GCM decrypt. Returns plaintext string."""
    key = _load_key(key_b64)
    aesgcm = AESGCM(key)
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()


def sign_request(payload: bytes, secret: str, timestamp: int | None = None) -> tuple[str, int]:
    """Sign a payload with HMAC-SHA256. Returns (signature_hex, timestamp)."""
    if timestamp is None:
        timestamp = int(time.time())
    msg = f"{timestamp}:".encode() + payload
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return sig, timestamp


def verify_request(
    payload: bytes,
    secret: str,
    signature: str,
    timestamp: int,
    window_seconds: int = 300,
) -> bool:
    """Verify HMAC signature and replay window."""
    now = int(time.time())
    if abs(now - timestamp) > window_seconds:
        return False
    expected, _ = sign_request(payload, secret, timestamp)
    return hmac.compare_digest(expected, signature)


def generate_key() -> str:
    """Generate a new base64-encoded 32-byte AES key."""
    return base64.b64encode(os.urandom(32)).decode()


def app_encrypt(value: str) -> str:
    """Encrypt *value* with the current app's ENCRYPTION_KEY.

    In test mode without a key, returns *value* unchanged for convenience.
    In non-test mode, raises RuntimeError if no key is configured to prevent
    silent plaintext writes.
    """
    try:
        from flask import current_app
        key = current_app.config.get('ENCRYPTION_KEY', '')
        if not key:
            if current_app.config.get('TESTING'):
                return value
            raise RuntimeError('ENCRYPTION_KEY is required for encrypting sensitive fields')
        return encrypt(value, key)
    except RuntimeError:
        raise
    except Exception:
        return value


def app_decrypt(value: str) -> str:
    """Decrypt *value* with the current app's ENCRYPTION_KEY.

    In test mode without a key, returns *value* unchanged for convenience.
    In non-test mode, raises RuntimeError if no key is configured.
    """
    try:
        from flask import current_app
        key = current_app.config.get('ENCRYPTION_KEY', '')
        if not key:
            if current_app.config.get('TESTING'):
                return value
            raise RuntimeError('ENCRYPTION_KEY is required for decrypting sensitive fields')
        return decrypt(value, key)
    except RuntimeError:
        raise
    except Exception:
        return value
