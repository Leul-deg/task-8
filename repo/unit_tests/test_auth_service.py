import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.services.auth_service import register_user, authenticate_user, change_password, deactivate_user

# Passwords that satisfy all strength requirements
VALID_PW = 'Secret1!'
VALID_PW2 = 'NewPass1!'


@pytest.fixture(scope='function')
def app():
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


class TestRegisterUser:
    def test_creates_user(self, db):
        user = register_user('alice', VALID_PW, 'alice@example.com')
        assert user.id is not None
        assert user.username == 'alice'

    def test_duplicate_username_raises(self, db):
        register_user('bob', VALID_PW)
        with pytest.raises(ValueError, match='already taken'):
            register_user('bob', VALID_PW)

    def test_duplicate_email_raises(self, db):
        register_user('carol', VALID_PW, 'carol@x.com')
        with pytest.raises(ValueError, match='already registered'):
            register_user('carol2', VALID_PW, 'carol@x.com')

    def test_password_is_hashed(self, db):
        user = register_user('dave', VALID_PW)
        assert user.password_hash != VALID_PW
        assert user.check_password(VALID_PW)


class TestAuthenticateUser:
    def test_valid_credentials(self, db, app):
        register_user('eve', VALID_PW)
        with app.test_request_context():
            user = authenticate_user('eve', VALID_PW)
        assert user is not None

    def test_invalid_password(self, db, app):
        register_user('frank', VALID_PW)
        with app.test_request_context():
            user = authenticate_user('frank', 'wrong')
        assert user is None

    def test_unknown_user(self, db, app):
        with app.test_request_context():
            user = authenticate_user('nobody', 'pass')
        assert user is None

    def test_inactive_user(self, db, app):
        u = register_user('ghost', VALID_PW)
        u.is_active = False
        _db.session.commit()
        with app.test_request_context():
            result = authenticate_user('ghost', VALID_PW)
        assert result is None


class TestChangePassword:
    def test_success(self, db):
        user = register_user('harry', VALID_PW)
        change_password(user, VALID_PW, VALID_PW2)
        assert user.check_password(VALID_PW2)

    def test_wrong_old_password(self, db):
        user = register_user('ivy', VALID_PW)
        with pytest.raises(ValueError, match='incorrect'):
            change_password(user, 'wrong', VALID_PW2)


class TestPasswordValidation:
    def test_register_short_password(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="at least 8 characters"):
                register_user(username='shortpw', password='Ab1!', full_name='Test')

    def test_register_no_uppercase(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="uppercase"):
                register_user(username='noup', password='abcdefg1!', full_name='Test')

    def test_register_no_digit(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="digit"):
                register_user(username='nodigit', password='Abcdefgh!', full_name='Test')

    def test_register_no_special(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="special"):
                register_user(username='nospec', password='Abcdefg1', full_name='Test')

    def test_register_valid_password(self, app):
        with app.app_context():
            user = register_user(username='goodpw', password='Abcdef1!', full_name='Test')
            assert user.id is not None


class TestStaffRoleAssignment:
    def test_staff_role_assigned_on_register(self, db):
        from app.models.user import Role
        staff_role = Role(name='staff', is_system=True)
        _db.session.add(staff_role)
        _db.session.commit()
        user = register_user('newstaff', VALID_PW, 'newstaff@example.com')
        assert any(r.name == 'staff' for r in user.roles)

    def test_no_staff_role_when_role_missing(self, db):
        """If staff role doesn't exist in DB, registration still succeeds."""
        user = register_user('norole', VALID_PW, 'norole@example.com')
        assert user.id is not None
        assert user.roles.count() == 0


class TestRateLimiter:
    """Rate-limit enforcement tests — require a custom app fixture with
    LOGIN_MAX_ATTEMPTS_PER_IP and LOGIN_MAX_ATTEMPTS_PER_USERNAME > 0."""

    @pytest.fixture
    def rate_limited_app(self):
        application = create_app('testing')
        application.config['LOGIN_MAX_ATTEMPTS_PER_IP'] = 3
        application.config['LOGIN_MAX_ATTEMPTS_PER_USERNAME'] = 3
        with application.app_context():
            _db.create_all()
            register_user('ratelimited', VALID_PW, 'rl@test.com')
            yield application
            _db.session.remove()
            _db.drop_all()

    @pytest.fixture
    def rl_client(self, rate_limited_app):
        return rate_limited_app.test_client()

    def _bad_login(self, client, times=1, username='ratelimited'):
        for _ in range(times):
            client.post('/auth/login', json={
                'username': username, 'password': 'wrongpass'
            })

    def test_ip_lockout_blocks_after_threshold(self, rl_client):
        """After max IP failures, the next attempt returns 429."""
        self._bad_login(rl_client, times=3)
        resp = rl_client.post('/auth/login', json={
            'username': 'ratelimited', 'password': 'wrongpass'
        })
        assert resp.status_code == 429
        data = resp.get_json()
        assert 'Too many' in data['error']

    def test_username_lockout_blocks_correct_password(self, rl_client):
        """After max failures, even the correct password is blocked with 429."""
        self._bad_login(rl_client, times=3)
        resp = rl_client.post('/auth/login', json={
            'username': 'ratelimited', 'password': VALID_PW
        })
        assert resp.status_code == 429

    def test_below_threshold_not_rate_limited(self, rl_client):
        """Exactly N-1 failures must not trigger lockout on the Nth attempt."""
        self._bad_login(rl_client, times=2)
        resp = rl_client.post('/auth/login', json={
            'username': 'ratelimited', 'password': 'wrongpass'
        })
        assert resp.status_code == 401  # still a normal auth failure, not 429

    def test_successful_login_not_counted_as_failure(self, rl_client):
        """Successful logins do not contribute to the failure counter."""
        self._bad_login(rl_client, times=2)
        resp = rl_client.post('/auth/login', json={
            'username': 'ratelimited', 'password': VALID_PW
        })
        assert resp.status_code == 200
        # 2 failures total — a success does not add to the count
        resp = rl_client.post('/auth/login', json={
            'username': 'ratelimited', 'password': VALID_PW
        })
        assert resp.status_code == 200

    def test_rate_limit_service_direct(self, rate_limited_app):
        """Service-level: _check_rate_limit raises RateLimitError after N recorded failures."""
        from app.services.auth_service import _check_rate_limit, RateLimitError
        from app.models.login_attempt import LoginAttempt

        with rate_limited_app.app_context():
            for _ in range(3):
                _db.session.add(LoginAttempt(key='user:directtest', succeeded=False))
            _db.session.commit()
            with pytest.raises(RateLimitError, match='Too many'):
                _check_rate_limit('user:directtest', 3, 900)
