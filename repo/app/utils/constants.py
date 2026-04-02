from enum import Enum


class OrgUnitLevel(str, Enum):
    CAMPUS = 'campus'
    COLLEGE = 'college'
    DEPARTMENT = 'department'
    SECTION = 'section'


class ListingStatus(str, Enum):
    DRAFT = 'draft'
    PENDING_REVIEW = 'pending_review'
    PUBLISHED = 'published'
    UNPUBLISHED = 'unpublished'
    EXPIRED = 'expired'
    LOCKED = 'locked'


class DrugForm(str, Enum):
    TABLET = 'tablet'
    CAPSULE = 'capsule'
    LIQUID = 'liquid'
    INJECTION = 'injection'
    TOPICAL = 'topical'
    INHALER = 'inhaler'
    PATCH = 'patch'
    OTHER = 'other'


class DrugStatus(str, Enum):
    DRAFT = 'draft'
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    ARCHIVED = 'archived'


class ModerationStatus(str, Enum):
    PENDING = 'pending'
    REVIEW_HIDDEN = 'review_hidden'
    REVIEW_RESTORED = 'review_restored'
    FINALIZED = 'finalized'


class AppealStatus(str, Enum):
    PENDING = 'pending'
    UPHELD = 'upheld'
    OVERTURNED = 'overturned'


class JobStatus(str, Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    DEAD_LETTER = 'dead_letter'


class ReviewerDisplayMode(str, Enum):
    FULL_NAME = 'full_name'
    INITIALS = 'initials'
    ANONYMOUS = 'anonymous'


class TagCategory(str, Enum):
    DRUG_CLASS = 'drug_class'
    ROUTE = 'route'
    INDICATION = 'indication'
    INTERACTION_RISK = 'interaction_risk'


PREDEFINED_REVIEW_TAGS = [
    'clear_instructions',
    'engaging',
    'well_organized',
    'practical',
    'too_fast',
    'too_slow',
    'outdated_content',
    'great_instructor',
    'needs_improvement',
    'highly_recommend',
]

DEFAULT_ROLES = [
    {'name': 'org_admin', 'description': 'Organization administrator with full access', 'is_system': True},
    {'name': 'property_manager', 'description': 'Manages property listings', 'is_system': True},
    {'name': 'instructor', 'description': 'Teaches training classes', 'is_system': True},
    {'name': 'content_moderator', 'description': 'Moderates reviews and content', 'is_system': True},
    {'name': 'staff', 'description': 'General staff member', 'is_system': True},
]

DEFAULT_PERMISSIONS = [
    # Listings
    {'codename': 'listing.create', 'description': 'Create property listings', 'category': 'listings'},
    {'codename': 'listing.edit', 'description': 'Edit property listings', 'category': 'listings'},
    {'codename': 'listing.publish', 'description': 'Publish property listings', 'category': 'listings'},
    {'codename': 'listing.delete', 'description': 'Delete property listings', 'category': 'listings'},
    {'codename': 'listing.lock', 'description': 'Lock property listings', 'category': 'listings'},
    # Classes
    {'codename': 'class.create', 'description': 'Create training classes', 'category': 'classes'},
    # Reviews
    {'codename': 'review.create', 'description': 'Create class reviews', 'category': 'reviews'},
    {'codename': 'review.moderate', 'description': 'Moderate class reviews', 'category': 'reviews'},
    {'codename': 'review.reply', 'description': 'Reply to class reviews', 'category': 'reviews'},
    # Drugs
    {'codename': 'drug.create', 'description': 'Create drug entries', 'category': 'drugs'},
    {'codename': 'drug.edit', 'description': 'Edit drug entries', 'category': 'drugs'},
    {'codename': 'drug.import', 'description': 'Import drug data', 'category': 'drugs'},
    {'codename': 'drug.approve', 'description': 'Approve drug entries', 'category': 'drugs'},
    # Admin
    {'codename': 'admin.users', 'description': 'Manage users', 'category': 'admin'},
    {'codename': 'admin.roles', 'description': 'Manage roles and permissions', 'category': 'admin'},
    {'codename': 'admin.org_units', 'description': 'Manage org units', 'category': 'admin'},
    {'codename': 'admin.audit_log', 'description': 'View audit logs', 'category': 'admin'},
    {'codename': 'admin.backup', 'description': 'Perform backups', 'category': 'admin'},
    {'codename': 'permission.grant', 'description': 'Grant temporary permissions', 'category': 'admin'},
]

MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
TEMP_GRANT_DEFAULT_HOURS = 72
REVIEW_APPEAL_WINDOW_DAYS = 14
APPEAL_RESOLUTION_DAYS = 5
BACKUP_RETENTION_DAYS = 30
HMAC_WINDOW_SECONDS = 300
