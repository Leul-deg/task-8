import re
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.moderation import ModerationReport, ModerationAppeal
from app.models.training import ClassReview
from app.models.user import User
from app.utils.constants import ModerationStatus, AppealStatus, REVIEW_APPEAL_WINDOW_DAYS, APPEAL_RESOLUTION_DAYS
from app.services.audit_service import log_action

KEYWORD_BLOCKLIST = [
    'hate', 'threat', 'kill', 'attack', 'racist', 'sexist',
    'harass', 'abuse', 'stupid', 'idiot', 'incompetent',
]


def scan_review_content(text: str) -> dict:
    if not text:
        return {'flagged': False, 'matches': []}
    matches = []
    text_lower = text.lower()
    for kw in KEYWORD_BLOCKLIST:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            matches.append(kw)
    return {'flagged': len(matches) > 0, 'matches': matches}


def auto_flag_review(review_id: int):
    review = db.session.get(ClassReview, review_id)
    if not review or not review.comment:
        return None
    result = scan_review_content(review.comment)
    if result['flagged']:
        review.is_visible = False
        review.is_moderated = True
        review.moderation_reason = 'Auto-flagged: blocked keywords detected'
        report = ModerationReport(
            review_id=review.id,
            reported_by_id=None,
            reason='Auto-flagged: blocked keywords detected',
            status=ModerationStatus.PENDING.value,
        )
        report.keyword_matches = result['matches']
        db.session.add(report)
        db.session.commit()
        log_action(
            action='moderation.auto_flag',
            resource_type='review',
            resource_id=review.id,
            new_value={'keywords': result['matches']},
        )
        return report
    return None


def report_review(review: ClassReview, reported_by: User, reason: str, keyword_matches: list | None = None) -> ModerationReport:
    if len(reason) < 10 or len(reason) > 500:
        raise ValueError("Report reason must be 10-500 characters")
    existing = ModerationReport.query.filter_by(review_id=review.id, reported_by_id=reported_by.id).first()
    if existing:
        raise ValueError("You have already reported this review")
    report = ModerationReport(
        review_id=review.id,
        reported_by_id=reported_by.id,
        reason=reason,
        status=ModerationStatus.PENDING.value,
    )
    report.keyword_matches = keyword_matches
    db.session.add(report)
    db.session.commit()
    log_action(
        action='moderation.report',
        resource_type='moderation_report',
        resource_id=report.id,
        user_id=reported_by.id,
        new_value={'review_id': review.id, 'reason': reason},
    )
    return report


def hide_review(report: ModerationReport, resolved_by: User, reason: str | None = None) -> ModerationReport:
    review = report.review
    review.is_visible = False
    review.is_moderated = True
    review.moderation_reason = reason
    report.status = ModerationStatus.REVIEW_HIDDEN.value
    report.resolved_by_id = resolved_by.id
    report.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='moderation.hide',
        resource_type='moderation_report',
        resource_id=report.id,
        user_id=resolved_by.id,
        new_value={'status': report.status},
    )
    return report


def restore_review(report: ModerationReport, resolved_by: User) -> ModerationReport:
    review = report.review
    review.is_visible = True
    review.is_moderated = False
    review.moderation_reason = None
    report.status = ModerationStatus.REVIEW_RESTORED.value
    report.resolved_by_id = resolved_by.id
    report.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='moderation.restore',
        resource_type='moderation_report',
        resource_id=report.id,
        user_id=resolved_by.id,
    )
    return report


def finalize_report(report: ModerationReport, resolved_by: User) -> ModerationReport:
    report.status = ModerationStatus.FINALIZED.value
    report.resolved_by_id = resolved_by.id
    report.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return report


def file_appeal(report: ModerationReport, appealed_by: User, appeal_text: str) -> ModerationAppeal:
    if report.status != ModerationStatus.REVIEW_HIDDEN.value:
        raise ValueError("Appeals can only be filed on hidden reviews")
    if report.review.reviewer_id != appealed_by.id:
        raise PermissionError("Only the review author can file an appeal")
    if len(appeal_text) < 20 or len(appeal_text) > 2000:
        raise ValueError("Appeal text must be 20-2000 characters")
    now = datetime.now(timezone.utc)
    resolved_at = report.resolved_at
    if resolved_at and resolved_at.tzinfo is None:
        resolved_at = resolved_at.replace(tzinfo=timezone.utc)
    if resolved_at:
        filing_deadline = resolved_at + timedelta(days=REVIEW_APPEAL_WINDOW_DAYS)
        if now > filing_deadline:
            raise ValueError("Appeal window has expired. Appeals must be filed within 14 calendar days.")
    resolution_deadline = _add_business_days(now, APPEAL_RESOLUTION_DAYS)
    appeal = ModerationAppeal(
        report_id=report.id,
        appealed_by_id=appealed_by.id,
        appeal_text=appeal_text,
        filed_at=now,
        deadline=resolved_at + timedelta(days=REVIEW_APPEAL_WINDOW_DAYS) if resolved_at else now + timedelta(days=REVIEW_APPEAL_WINDOW_DAYS),
        resolution_deadline=resolution_deadline,
        status=AppealStatus.PENDING.value,
    )
    db.session.add(appeal)
    db.session.commit()
    log_action(
        action='moderation.appeal',
        resource_type='moderation_appeal',
        resource_id=appeal.id,
        user_id=appealed_by.id,
    )
    return appeal


def resolve_appeal(
    appeal: ModerationAppeal,
    resolved_by: User,
    decision: str,
    notes: str | None = None,
) -> ModerationAppeal:
    if decision not in (AppealStatus.UPHELD.value, AppealStatus.OVERTURNED.value):
        raise ValueError("Decision must be 'upheld' or 'overturned'")
    now = datetime.now(timezone.utc)
    deadline = appeal.resolution_deadline
    if deadline and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline and now > deadline:
        raise ValueError("Appeal resolution deadline has passed")
    appeal.status = decision
    appeal.resolved_by_id = resolved_by.id
    appeal.resolved_at = now
    appeal.resolution_notes = notes
    if decision == AppealStatus.OVERTURNED.value:
        restore_review(appeal.report, resolved_by)
    db.session.commit()
    log_action(
        action='moderation.appeal_resolve',
        resource_type='moderation_appeal',
        resource_id=appeal.id,
        user_id=resolved_by.id,
        new_value={'decision': decision},
    )
    return appeal


def _add_business_days(start: datetime, days: int) -> datetime:
    current = start
    added = 0
    while added < days:
        current = current + timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current
