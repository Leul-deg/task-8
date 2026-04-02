from datetime import datetime, timezone
from app.extensions import db
from app.utils.constants import OrgUnitLevel


class OrgUnit(db.Model):
    __tablename__ = 'org_unit'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False)
    level = db.Column(db.String(20), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('org_unit.id'), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    reviewer_display_mode = db.Column(
        db.String(20),
        nullable=False,
        default='anonymous',
        server_default='anonymous',
    )
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    parent = db.relationship('OrgUnit', remote_side=[id], back_populates='children')
    children = db.relationship('OrgUnit', back_populates='parent', cascade='all, delete-orphan')
    members = db.relationship('UserOrgUnit', back_populates='org_unit', cascade='all, delete-orphan')

    def get_ancestors(self) -> list['OrgUnit']:
        ancestors = []
        current = self.parent
        while current is not None:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def get_descendants(self) -> list['OrgUnit']:
        result = []
        stack = list(self.children)
        while stack:
            node = stack.pop()
            result.append(node)
            stack.extend(node.children)
        return result

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'level': self.level,
            'parent_id': self.parent_id,
            'is_active': self.is_active,
            'reviewer_display_mode': self.reviewer_display_mode,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f'<OrgUnit {self.code}: {self.name}>'


class UserOrgUnit(db.Model):
    __tablename__ = 'user_org_unit'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    org_unit_id = db.Column(db.Integer, db.ForeignKey('org_unit.id'), primary_key=True)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship('User', back_populates='org_memberships')
    org_unit = db.relationship('OrgUnit', back_populates='members')

    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'org_unit_id': self.org_unit_id,
            'is_primary': self.is_primary,
        }
