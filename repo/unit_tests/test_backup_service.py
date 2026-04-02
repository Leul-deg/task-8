"""Tests for backup_service: encryption, pruning, and listing."""
import base64
import os
import sqlite3
import time

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app import create_app
from app.extensions import db as _db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='function')
def app(tmp_path):
    """App instance whose ENCRYPTION_KEY is set to a fresh random key."""
    key = base64.b64encode(os.urandom(32)).decode()
    application = create_app('testing')
    application.config['ENCRYPTION_KEY'] = key
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def src_db(tmp_path):
    """A minimal real SQLite file to serve as the backup source."""
    p = tmp_path / 'source.db'
    conn = sqlite3.connect(str(p))
    conn.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)')
    conn.execute("INSERT INTO t VALUES (1, 'hello')")
    conn.commit()
    conn.close()
    return str(p)


@pytest.fixture
def backup_dir(tmp_path):
    d = tmp_path / 'backups'
    d.mkdir()
    return str(d)


# ---------------------------------------------------------------------------
# create_backup
# ---------------------------------------------------------------------------

class TestCreateBackup:
    def test_creates_enc_file(self, app, src_db, backup_dir):
        from app.services.backup_service import create_backup
        enc_path = create_backup(src_db, backup_dir)
        assert enc_path.endswith('.enc')
        assert os.path.exists(enc_path)

    def test_plaintext_file_removed(self, app, src_db, backup_dir):
        from app.services.backup_service import create_backup
        create_backup(src_db, backup_dir)
        # No bare .db files should remain
        db_files = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
        assert db_files == []

    def test_enc_file_is_valid_sqlite_when_decrypted(self, app, src_db, backup_dir):
        from app.services.backup_service import create_backup
        enc_path = create_backup(src_db, backup_dir)

        key = base64.b64decode(app.config['ENCRYPTION_KEY'])
        raw = open(enc_path, 'rb').read()
        plaintext = AESGCM(key).decrypt(raw[:12], raw[12:], None)

        # Write decrypted bytes to a temp file and open as SQLite.
        dec_path = enc_path.replace('.enc', '.dec')
        open(dec_path, 'wb').write(plaintext)
        conn = sqlite3.connect(dec_path)
        rows = conn.execute('SELECT val FROM t').fetchall()
        conn.close()
        assert rows == [('hello',)]

    def test_missing_encryption_key_raises(self, app, src_db, backup_dir):
        from app.services.backup_service import create_backup
        app.config['ENCRYPTION_KEY'] = ''
        with pytest.raises(RuntimeError, match='ENCRYPTION_KEY'):
            create_backup(src_db, backup_dir)

    def test_backup_logged_to_audit(self, app, db, src_db, backup_dir):
        from app.services.backup_service import create_backup
        from app.models.audit import AuditLog
        create_backup(src_db, backup_dir)
        log = AuditLog.query.filter_by(action='backup.create').first()
        assert log is not None
        assert '.enc' in log.new_value

    def test_backup_creates_dir_if_missing(self, app, src_db, tmp_path):
        from app.services.backup_service import create_backup
        new_dir = str(tmp_path / 'new_backup_dir')
        assert not os.path.exists(new_dir)
        create_backup(src_db, new_dir)
        assert os.path.isdir(new_dir)


# ---------------------------------------------------------------------------
# prune_old_backups
# ---------------------------------------------------------------------------

class TestPruneOldBackups:
    def _make_file(self, backup_dir, name, age_seconds):
        p = os.path.join(backup_dir, name)
        open(p, 'wb').write(b'dummy')
        mtime = time.time() - age_seconds
        os.utime(p, (mtime, mtime))
        return p

    def test_removes_files_older_than_retention(self, app, backup_dir):
        from app.services.backup_service import prune_old_backups
        old = self._make_file(backup_dir, 'old.enc', 31 * 86400)
        prune_old_backups(backup_dir, retention_days=30)
        assert not os.path.exists(old)

    def test_keeps_files_within_retention(self, app, backup_dir):
        from app.services.backup_service import prune_old_backups
        recent = self._make_file(backup_dir, 'recent.enc', 5 * 86400)
        prune_old_backups(backup_dir, retention_days=30)
        assert os.path.exists(recent)

    def test_returns_count_of_deleted_files(self, app, backup_dir):
        from app.services.backup_service import prune_old_backups
        self._make_file(backup_dir, 'a.enc', 31 * 86400)
        self._make_file(backup_dir, 'b.enc', 32 * 86400)
        self._make_file(backup_dir, 'c.enc', 1 * 86400)
        deleted = prune_old_backups(backup_dir, retention_days=30)
        assert deleted == 2

    def test_nonexistent_dir_returns_zero(self, app, tmp_path):
        from app.services.backup_service import prune_old_backups
        deleted = prune_old_backups(str(tmp_path / 'no_such_dir'), retention_days=30)
        assert deleted == 0


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------

class TestListBackups:
    def test_returns_empty_for_missing_dir(self, app, tmp_path):
        from app.services.backup_service import list_backups
        result = list_backups(str(tmp_path / 'no_such_dir'))
        assert result == []

    def test_lists_all_files(self, app, src_db, backup_dir):
        from app.services.backup_service import create_backup, list_backups
        create_backup(src_db, backup_dir)
        result = list_backups(backup_dir)
        assert len(result) >= 1

    def test_entry_has_required_keys(self, app, src_db, backup_dir):
        from app.services.backup_service import create_backup, list_backups
        create_backup(src_db, backup_dir)
        entry = list_backups(backup_dir)[0]
        assert 'filename' in entry
        assert 'size_bytes' in entry
        assert 'created' in entry

    def test_enc_files_listed(self, app, src_db, backup_dir):
        from app.services.backup_service import create_backup, list_backups
        create_backup(src_db, backup_dir)
        result = list_backups(backup_dir)
        assert all(e['filename'].endswith('.enc') for e in result)
