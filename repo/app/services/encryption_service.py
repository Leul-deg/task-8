from flask import current_app
from app.utils.crypto import encrypt, decrypt, generate_key


def encrypt_value(plaintext: str) -> str:
    key = current_app.config['ENCRYPTION_KEY']
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return encrypt(plaintext, key)


def decrypt_value(token: str) -> str:
    key = current_app.config['ENCRYPTION_KEY']
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return decrypt(token, key)


def rotate_key(old_key_b64: str, new_key_b64: str, ciphertext: str) -> str:
    """Re-encrypt a ciphertext under a new key."""
    plaintext = decrypt(ciphertext, old_key_b64)
    return encrypt(plaintext, new_key_b64)
