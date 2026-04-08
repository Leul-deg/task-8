import hashlib
import re
from datetime import datetime, timezone, timedelta
from flask import current_app
from flask_login import login_user, logout_user
from app.extensions import db
from app.models.user import User
from app.models.login_attempt import LoginAttempt
from app.services.audit_service import log_action


class RateLimitError(Exception):
    """Raised when a login attempt is blocked by the rate limiter."""


def _record_attempt(key: str, succeeded: bool) -> None:
    db.session.add(LoginAttempt(key=key, succeeded=succeeded))
    db.session.commit()


def _check_rate_limit(key: str, max_failures: int, window_seconds: int) -> None:
    """Raise RateLimitError if too many recent failures for *key*."""
    if max_failures == 0:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    # Prune old rows for this key to keep the table bounded.
    LoginAttempt.query.filter(
        LoginAttempt.key == key,
        LoginAttempt.attempted_at < cutoff,
    ).delete(synchronize_session=False)
    recent_failures = LoginAttempt.query.filter(
        LoginAttempt.key == key,
        LoginAttempt.succeeded == False,
        LoginAttempt.attempted_at >= cutoff,
    ).count()
    if recent_failures >= max_failures:
        raise RateLimitError(f'Too many failed login attempts. Try again later.')


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r'[A-Z]', password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r'\d', password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*()\-_+=]', password):
        raise ValueError("Password must contain at least one special character")


def register_user(
    username: str,
    password: str,
    email: str | None = None,
    full_name: str | None = None,
    org_unit_ids: list[int] | None = None,
) -> User:
    _validate_password_strength(password)
    if User.query.filter_by(username=username).first():
        raise ValueError(f"Username '{username}' is already taken")
    normalized_email = User.normalize_email(email) if email else None
    if normalized_email:
        email_hash = hashlib.sha256(normalized_email.encode('utf-8')).hexdigest()
        if User.query.filter_by(email_hash=email_hash).first():
            raise ValueError(f"Email '{email}' is already registered")

    user = User(username=username, email=email, full_name=full_name)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    from app.models.user import Role
    staff_role = Role.query.filter_by(name='staff').first()
    if staff_role:
        user.roles.append(staff_role)

    from app.models.organization import UserOrgUnit
    for i, uid in enumerate(org_unit_ids or []):
        db.session.add(UserOrgUnit(user_id=user.id, org_unit_id=uid, is_primary=(i == 0)))

    db.session.commit()
    log_action(
        action='user.register',
        resource_type='user',
        resource_id=user.id,
        new_value={'username': username, 'email': email},
    )
    return user


def authenticate_user(username: str, password: str, ip_address: str | None = None) -> User | None:
    """Authenticate a user by username and password.

    Raises RateLimitError if the IP address or username has too many recent
    failures.  Callers must catch RateLimitError and return HTTP 429.
    """
    max_per_ip = current_app.config.get('LOGIN_MAX_ATTEMPTS_PER_IP', 20)
    max_per_user = current_app.config.get('LOGIN_MAX_ATTEMPTS_PER_USERNAME', 10)
    window = current_app.config.get('LOGIN_RATE_WINDOW_SECONDS', 900)

    if ip_address:
        _check_rate_limit(f'ip:{ip_address}', max_per_ip, window)
    _check_rate_limit(f'user:{username}', max_per_user, window)

    user = User.query.filter_by(username=username).first()
    if user and user.is_active and user.check_password(password):
        if ip_address:
            _record_attempt(f'ip:{ip_address}', succeeded=True)
        _record_attempt(f'user:{username}', succeeded=True)
        login_user(user)
        log_action(
            action='user.login',
            resource_type='user',
            resource_id=user.id,
            user_id=user.id,
            ip_address=ip_address,
        )
        return user

    if ip_address:
        _record_attempt(f'ip:{ip_address}', succeeded=False)
    _record_attempt(f'user:{username}', succeeded=False)
    log_action(
        action='user.login_failed',
        resource_type='user',
        resource_id=None,
        new_value={'username': username},
        ip_address=ip_address,
    )
    return None


def logout_current_user(user_id: int | None = None) -> None:
    logout_user()
    if user_id:
        log_action(
            action='user.logout',
            resource_type='user',
            resource_id=user_id,
            user_id=user_id,
        )


def change_password(user: User, old_password: str, new_password: str) -> None:
    if not user.check_password(old_password):
        raise ValueError("Current password is incorrect")
    _validate_password_strength(new_password)
    user.set_password(new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='user.password_change',
        resource_type='user',
        resource_id=user.id,
        user_id=user.id,
    )


def deactivate_user(user: User, admin_id: int) -> None:
    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='user.deactivate',
        resource_type='user',
        resource_id=user.id,
        user_id=admin_id,
    )


def activate_user(user: User, admin_id: int) -> None:
    user.is_active = True
    user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='user.activate',
        resource_type='user',
        resource_id=user.id,
        user_id=admin_id,
    )
