from datetime import datetime, timezone
from app.extensions import db
from app.utils.constants import ListingStatus
from app.utils.crypto import app_encrypt, app_decrypt


class PropertyListing(db.Model):
    __tablename__ = 'property_listing'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    _address_line1 = db.Column('address_line1', db.String(255), nullable=False)
    _address_line2 = db.Column('address_line2', db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    floor_plan_notes = db.Column(db.Text, nullable=True)
    square_footage = db.Column(db.Integer, nullable=True)
    monthly_rent_cents = db.Column(db.Integer, nullable=False)
    deposit_cents = db.Column(db.Integer, nullable=False)
    lease_start = db.Column(db.Date, nullable=False)
    lease_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ListingStatus.DRAFT.value)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    org_unit_id = db.Column(db.Integer, db.ForeignKey('org_unit.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    published_at = db.Column(db.DateTime, nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)
    locked_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    locked_by = db.relationship('User', foreign_keys=[locked_by_id])
    org_unit = db.relationship('OrgUnit')
    amenities = db.relationship('ListingAmenity', back_populates='listing', cascade='all, delete-orphan')
    status_history = db.relationship(
        'ListingStatusHistory', back_populates='listing', cascade='all, delete-orphan',
        order_by='ListingStatusHistory.changed_at',
    )

    @property
    def address_line1(self):
        if self._address_line1:
            try:
                return app_decrypt(self._address_line1)
            except Exception:
                return self._address_line1
        return None

    @address_line1.setter
    def address_line1(self, value):
        if value:
            self._address_line1 = app_encrypt(value)
        else:
            self._address_line1 = None

    @property
    def address_line2(self):
        if self._address_line2:
            try:
                return app_decrypt(self._address_line2)
            except Exception:
                return self._address_line2
        return None

    @address_line2.setter
    def address_line2(self, value):
        if value:
            self._address_line2 = app_encrypt(value)
        else:
            self._address_line2 = None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'address_line1': self.address_line1,
            'address_line2': self.address_line2,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'floor_plan_notes': self.floor_plan_notes,
            'square_footage': self.square_footage,
            'monthly_rent_cents': self.monthly_rent_cents,
            'deposit_cents': self.deposit_cents,
            'lease_start': self.lease_start.isoformat() if self.lease_start else None,
            'lease_end': self.lease_end.isoformat() if self.lease_end else None,
            'status': self.status,
            'created_by_id': self.created_by_id,
            'org_unit_id': self.org_unit_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'locked_at': self.locked_at.isoformat() if self.locked_at else None,
            'locked_by_id': self.locked_by_id,
            'amenities': [a.name for a in self.amenities],
        }

    def __repr__(self) -> str:
        return f'<PropertyListing {self.id}: {self.title}>'


class ListingAmenity(db.Model):
    __tablename__ = 'listing_amenity'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('property_listing.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)

    listing = db.relationship('PropertyListing', back_populates='amenities')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'listing_id': self.listing_id,
            'name': self.name,
        }


class ListingStatusHistory(db.Model):
    __tablename__ = 'listing_status_history'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('property_listing.id'), nullable=False, index=True)
    old_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    listing = db.relationship('PropertyListing', back_populates='status_history')
    changed_by = db.relationship('User')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'listing_id': self.listing_id,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'changed_by_id': self.changed_by_id,
            'reason': self.reason,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
        }
