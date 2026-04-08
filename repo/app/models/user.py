import hashlib
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.utils.crypto import app_encrypt, app_decrypt

user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
)

role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True),
)



class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    _email = db.Column('email', db.String(200), nullable=True)
    email_hash = db.Column(db.String(64), unique=True, nullable=True, index=True)
    _full_name = db.Column('full_name', db.String(200), nullable=True)
    display_preference = db.Column(
        db.String(20),
        nullable=False,
        default='anonymous',
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __init__(self, **kwargs):
        kwargs.setdefault('is_active', True)
        kwargs.setdefault('display_preference', 'anonymous')
        super().__init__(**kwargs)

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    roles = db.relationship('Role', secondary=user_roles, back_populates='users', lazy='dynamic')
    org_memberships = db.relationship('UserOrgUnit', back_populates='user', cascade='all, delete-orphan')
    temp_grants = db.relationship(
        'TempGrant',
        foreign_keys='TempGrant.user_id',
        back_populates='user',
        cascade='all, delete-orphan',
    )

    @property
    def email(self):
        if self._email:
            try:
                return app_decrypt(self._email)
            except Exception:
                return self._email
        return None

    @email.setter
    def email(self, value):
        if value:
            normalized = self.normalize_email(value)
            self._email = app_encrypt(value)
            self.email_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        else:
            self._email = None
            self.email_hash = None

    @property
    def full_name(self):
        if self._full_name:
            try:
                return app_decrypt(self._full_name)
            except Exception:
                return self._full_name
        return None

    @full_name.setter
    def full_name(self, value):
        if value:
            self._full_name = app_encrypt(value)
        else:
            self._full_name = None

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    @staticmethod
    def normalize_email(value: str) -> str:
        return value.strip().lower()

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_display_name(self) -> str:
        pref = self.display_preference
        if pref == 'full_name' and self.full_name:
            return self.full_name
        if pref == 'initials' and self.full_name:
            parts = self.full_name.split()
            return ''.join(p[0].upper() for p in parts if p)
        return 'Anonymous'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'display_preference': self.display_preference,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'roles': [r.name for r in self.roles],
        }

    def __repr__(self) -> str:
        return f'<User {self.username}>'


class Role(db.Model):
    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    users = db.relationship('User', secondary=user_roles, back_populates='roles', lazy='dynamic')
    permissions = db.relationship('Permission', secondary=role_permissions, back_populates='roles', lazy='dynamic')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'permissions': [p.codename for p in self.permissions],
        }

    def __repr__(self) -> str:
        return f'<Role {self.name}>'


class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    codename = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(64), nullable=False)

    roles = db.relationship('Role', secondary=role_permissions, back_populates='permissions', lazy='dynamic')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'codename': self.codename,
            'description': self.description,
            'category': self.category,
        }

    def __repr__(self) -> str:
        return f'<Permission {self.codename}>'


class TempGrant(db.Model):
    __tablename__ = 'temp_grant'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=False)
    granted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    granted_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], back_populates='temp_grants')
    permission = db.relationship('Permission')
    granted_by = db.relationship('User', foreign_keys=[granted_by_id])
    revoked_by = db.relationship('User', foreign_keys=[revoked_by_id])

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'permission_id': self.permission_id,
            'permission_codename': self.permission.codename if self.permission else None,
            'granted_by_id': self.granted_by_id,
            'reason': self.reason,
            'granted_at': self.granted_at.isoformat() if self.granted_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'revoked_by_id': self.revoked_by_id,
        }
