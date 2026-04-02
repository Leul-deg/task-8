from datetime import datetime, timezone
from app.extensions import db
from app.utils.constants import DrugForm, DrugStatus


drug_tags = db.Table(
    'drug_tag',
    db.Column('drug_id', db.Integer, db.ForeignKey('drug.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag_taxonomy.id'), primary_key=True),
)


class Drug(db.Model):
    __tablename__ = 'drug'

    id = db.Column(db.Integer, primary_key=True)
    generic_name = db.Column(db.String(255), nullable=False, index=True)
    brand_name = db.Column(db.String(255), nullable=True)
    strength = db.Column(db.String(64), nullable=False)
    form = db.Column(db.String(20), nullable=False)
    ndc_code = db.Column(db.String(20), nullable=True)
    description = db.Column(db.Text, nullable=True)
    contraindications = db.Column(db.Text, nullable=True)
    side_effects = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=DrugStatus.DRAFT.value)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    approved_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('generic_name', 'strength', 'form', name='uq_drug_generic_strength_form'),
    )

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])
    tags = db.relationship('TagTaxonomy', secondary=drug_tags, back_populates='drugs', lazy='dynamic')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'generic_name': self.generic_name,
            'brand_name': self.brand_name,
            'strength': self.strength,
            'form': self.form,
            'ndc_code': self.ndc_code,
            'description': self.description,
            'contraindications': self.contraindications,
            'side_effects': self.side_effects,
            'status': self.status,
            'created_by_id': self.created_by_id,
            'approved_by_id': self.approved_by_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'tags': [t.name for t in self.tags],
        }

    def __repr__(self) -> str:
        return f'<Drug {self.id}: {self.generic_name} {self.strength}>'


class TagTaxonomy(db.Model):
    __tablename__ = 'tag_taxonomy'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    category = db.Column(db.String(64), nullable=False)
    is_controlled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    drugs = db.relationship('Drug', secondary=drug_tags, back_populates='tags', lazy='dynamic')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'is_controlled': self.is_controlled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
