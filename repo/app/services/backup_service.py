import base64
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app
from app.services.audit_service import log_action


def create_backup(db_path: str, backup_dir: str) -> str:
    """Back up the SQLite database and encrypt the result with AES-GCM."""
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    plain_path = os.path.join(backup_dir, f'backup_{timestamp}.db')

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(plain_path)
    src.backup(dst)
    dst.close()
    src.close()

    key_b64 = current_app.config.get('ENCRYPTION_KEY', '')
    if not key_b64:
        raise RuntimeError('ENCRYPTION_KEY is not set; refusing to write an unencrypted backup')

    key = base64.b64decode(key_b64)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = open(plain_path, 'rb').read()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    enc_path = plain_path + '.enc'
    with open(enc_path, 'wb') as f:
        f.write(nonce + ciphertext)

    os.remove(plain_path)

    log_action(
        action='backup.create',
        resource_type='backup',
        new_value={'backup_path': enc_path},
    )
    return enc_path


def prune_old_backups(backup_dir: str, retention_days: int | None = None) -> int:
    """Delete backup files older than retention_days. Returns count deleted."""
    if retention_days is None:
        try:
            retention_days = current_app.config.get('BACKUP_RETENTION_DAYS', 30)
        except RuntimeError:
            retention_days = 30
    cutoff = time.time() - (retention_days * 86400)
    count = 0
    if not os.path.exists(backup_dir):
        return 0
    for f in os.listdir(backup_dir):
        fp = os.path.join(backup_dir, f)
        if os.path.isfile(fp) and os.path.getmtime(fp) < cutoff:
            os.remove(fp)
            count += 1
    return count


def restore_backup(backup_dir: str, filename: str, db_path: str, *, dry_run: bool = False) -> dict:
    """Decrypt and restore a backup file. If dry_run=True, only validate without overwriting."""
    if not filename.endswith('.enc'):
        raise ValueError('Only encrypted backup files (.enc) can be restored')

    enc_path = os.path.join(backup_dir, filename)
    if not os.path.isfile(enc_path):
        raise FileNotFoundError(f'Backup file not found: {filename}')

    key_b64 = current_app.config.get('ENCRYPTION_KEY', '')
    if not key_b64:
        raise RuntimeError('ENCRYPTION_KEY is not set; cannot decrypt backup')

    key = base64.b64decode(key_b64)
    aesgcm = AESGCM(key)

    raw = open(enc_path, 'rb').read()
    nonce = raw[:12]
    ciphertext = raw[12:]
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError('Decryption failed — file may be corrupt or key mismatch')

    temp_path = enc_path + '.restore_tmp'
    try:
        with open(temp_path, 'wb') as f:
            f.write(plaintext)

        conn = sqlite3.connect(temp_path)
        try:
            result = conn.execute('PRAGMA integrity_check').fetchone()
            valid = result and result[0] == 'ok'
        finally:
            conn.close()

        if not valid:
            raise ValueError('Backup integrity check failed — database is corrupt')

        if dry_run:
            return {'status': 'valid', 'filename': filename, 'dry_run': True}

        src = sqlite3.connect(temp_path)
        dst = sqlite3.connect(db_path)
        src.backup(dst)
        dst.close()
        src.close()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    log_action(
        action='backup.restore',
        resource_type='backup',
        new_value={'filename': filename, 'dry_run': dry_run},
    )
    return {'status': 'restored', 'filename': filename, 'dry_run': False}


def list_backups(backup_dir: str) -> list:
    if not os.path.exists(backup_dir):
        return []
    backups = []
    for f in sorted(os.listdir(backup_dir), reverse=True):
        fp = os.path.join(backup_dir, f)
        if os.path.isfile(fp):
            backups.append({
                'filename': f,
                'size_bytes': os.path.getsize(fp),
                'created': datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
            })
    return backups
