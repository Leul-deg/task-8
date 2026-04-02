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
