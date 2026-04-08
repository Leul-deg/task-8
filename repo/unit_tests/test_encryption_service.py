import pytest
import base64
import os
from app import create_app
from app.extensions import db as _db
from app.utils.crypto import encrypt, decrypt, sign_request, verify_request, generate_key


VALID_KEY = base64.b64encode(b'\xab' * 32).decode()


@pytest.fixture(scope='function')
def encrypted_app():
    """App with ENCRYPTION_KEY configured."""
    application = create_app('testing')
    application.config['ENCRYPTION_KEY'] = VALID_KEY
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def plain_app():
    """App without ENCRYPTION_KEY (plaintext storage)."""
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


class TestCrypto:
    def setup_method(self):
        self.key = base64.b64encode(os.urandom(32)).decode()

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = 'Hello, clinical portal!'
        token = encrypt(plaintext, self.key)
        assert decrypt(token, self.key) == plaintext

    def test_different_ciphertexts(self):
        # Each encryption should produce a different ciphertext (nonce is random)
        t1 = encrypt('same', self.key)
        t2 = encrypt('same', self.key)
        assert t1 != t2

    def test_wrong_key_raises(self):
        other_key = base64.b64encode(os.urandom(32)).decode()
        token = encrypt('secret', self.key)
        from cryptography.exceptions import InvalidTag
        with pytest.raises(Exception):
            decrypt(token, other_key)

    def test_generate_key(self):
        key = generate_key()
        raw = base64.b64decode(key)
        assert len(raw) == 32


class TestHmac:
    def test_sign_and_verify(self):
        payload = b'test body'
        secret = 'my-secret'
        sig, ts = sign_request(payload, secret)
        assert verify_request(payload, secret, sig, ts)

    def test_wrong_secret(self):
        payload = b'body'
        sig, ts = sign_request(payload, 'secret')
        assert not verify_request(payload, 'wrong-secret', sig, ts)

    def test_replay_window_expired(self):
        import time
        payload = b'body'
        sig, ts = sign_request(payload, 'secret', timestamp=int(time.time()) - 400)
        assert not verify_request(payload, 'secret', sig, ts, window_seconds=300)


class TestUserEmailEncryption:
    def test_email_stored_encrypted(self, encrypted_app):
        from app.models.user import User
        user = User(username='alice')
        user.set_password('Secret1!')
        user.email = 'alice@example.com'
        _db.session.add(user)
        _db.session.commit()
        raw = _db.session.execute(
            _db.text('SELECT email FROM user WHERE id = :id'), {'id': user.id}
        ).scalar()
        assert raw != 'alice@example.com'

    def test_email_decrypts_correctly(self, encrypted_app):
        from app.models.user import User
        user = User(username='bob')
        user.set_password('Secret1!')
        user.email = 'bob@example.com'
        _db.session.add(user)
        _db.session.commit()
        _db.session.expire(user)
        assert user.email == 'bob@example.com'

    def test_same_email_reencrypts_to_different_ciphertext_but_same_hash(self, encrypted_app):
        """Re-setting the same email changes ciphertext but keeps the uniqueness hash stable."""
        from app.models.user import User
        u1 = User(username='carol')
        u1.set_password('Secret1!')
        u1.email = 'same@example.com'
        _db.session.add(u1)
        _db.session.commit()
        raw1 = _db.session.execute(
            _db.text('SELECT email, email_hash FROM user WHERE id = :id'), {'id': u1.id}
        ).scalar()
        hash1 = _db.session.execute(
            _db.text('SELECT email_hash FROM user WHERE id = :id'), {'id': u1.id}
        ).scalar()
        u1.email = 'same@example.com'
        _db.session.commit()
        raw2 = _db.session.execute(
            _db.text('SELECT email FROM user WHERE id = :id'), {'id': u1.id}
        ).scalar()
        hash2 = _db.session.execute(
            _db.text('SELECT email_hash FROM user WHERE id = :id'), {'id': u1.id}
        ).scalar()
        assert raw1 != raw2
        assert hash1 == hash2

    def test_no_key_stores_plaintext_in_test_mode(self, plain_app):
        from app.models.user import User
        user = User(username='frank')
        user.set_password('Secret1!')
        user.email = 'frank@example.com'
        _db.session.add(user)
        _db.session.commit()
        assert user.email == 'frank@example.com'


class TestEncryptionKeyEnforcement:
    """Verify that missing ENCRYPTION_KEY is rejected in non-test modes."""

    def test_create_app_fails_without_key_in_dev_mode(self):
        with pytest.raises(RuntimeError, match='ENCRYPTION_KEY must be set'):
            app = create_app('development')

    def test_create_app_ok_without_key_in_test_mode(self):
        app = create_app('testing')
        assert app.config['TESTING'] is True

    def test_app_encrypt_raises_without_key_in_non_test(self):
        from app.utils.crypto import app_encrypt
        from flask import Flask
        app = Flask(__name__)
        app.config['TESTING'] = False
        app.config['ENCRYPTION_KEY'] = ''
        with app.app_context():
            with pytest.raises(RuntimeError, match='ENCRYPTION_KEY is required'):
                app_encrypt('sensitive-data')

    def test_app_decrypt_raises_without_key_in_non_test(self):
        from app.utils.crypto import app_decrypt
        from flask import Flask
        app = Flask(__name__)
        app.config['TESTING'] = False
        app.config['ENCRYPTION_KEY'] = ''
        with app.app_context():
            with pytest.raises(RuntimeError, match='ENCRYPTION_KEY is required'):
                app_decrypt('some-token')

    def test_validate_security_config_rejects_placeholder_prod_secrets(self):
        from flask import Flask
        from app import _validate_security_config

        app = Flask(__name__)
        app.config['TESTING'] = False
        app.config['DEBUG'] = False
        app.config['FLASK_ENV'] = 'production'
        app.config['SECRET_KEY'] = 'change-me-in-production-secret-key'
        app.config['HMAC_SECRET'] = 'change-me-in-production-hmac-secret'
        app.config['ENCRYPTION_KEY'] = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            with app.app_context():
                _validate_security_config(app)
