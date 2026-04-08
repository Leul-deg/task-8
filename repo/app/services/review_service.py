from datetime import datetime, timezone
from app.extensions import db
from app.models.training import ClassReview, CoachReply, TrainingClass, ClassAttendee
from app.models.user import User
from app.services.audit_service import log_action
from app.utils.validators import validate_rating, validate_review_comment, validate_review_tags


def create_review(class_id: int, reviewer: User, data: dict) -> ClassReview:
    training_class = TrainingClass.query.get_or_404(class_id)
    from app.services.permission_service import user_accessible_org_ids
    accessible_orgs = user_accessible_org_ids(reviewer)
    if not accessible_orgs:
        raise PermissionError("You do not have access to this class")
    if training_class.org_unit_id not in accessible_orgs:
        raise PermissionError("You do not have access to this class")
    attendee = ClassAttendee.query.filter_by(class_id=class_id, user_id=reviewer.id, attended=True).first()
    if not attendee:
        raise PermissionError("Only verified attendees can review a class")
    existing = ClassReview.query.filter_by(class_id=class_id, reviewer_id=reviewer.id).first()
    if existing:
        raise ValueError("You have already reviewed this class")
    rating = validate_rating(data['rating'])
    comment = validate_review_comment(data.get('comment'))
    tags = validate_review_tags(data.get('tags', []))
    review = ClassReview(
        class_id=class_id,
        reviewer_id=reviewer.id,
        rating=rating,
        comment=comment,
    )
    review.tags = tags
    db.session.add(review)
    db.session.commit()
    log_action(
        action='review.create',
        resource_type='review',
        resource_id=review.id,
        user_id=reviewer.id,
        new_value=review.to_dict(),
    )
    from app.services.moderation_service import auto_flag_review
    auto_flag_review(review.id)
    return review


def update_review(review: ClassReview, reviewer: User, data: dict) -> ClassReview:
    if review.reviewer_id != reviewer.id:
        raise PermissionError("Cannot edit another user's review")
    if review.is_moderated:
        raise ValueError("This review is under moderation and cannot be edited")
    old = review.to_dict()
    if 'rating' in data:
        review.rating = validate_rating(data['rating'])
    if 'comment' in data:
        review.comment = validate_review_comment(data['comment'])
    if 'tags' in data:
        review.tags = validate_review_tags(data['tags'])
    review.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(
        action='review.update',
        resource_type='review',
        resource_id=review.id,
        user_id=reviewer.id,
        old_value=old,
        new_value=review.to_dict(),
    )
    from app.services.moderation_service import auto_flag_review
    auto_flag_review(review.id)
    return review


def add_coach_reply(review: ClassReview, instructor: User, body: str) -> CoachReply:
    if review.training_class.instructor_id != instructor.id:
        raise PermissionError("Only the class instructor can reply to reviews")
    if review.coach_reply:
        raise ValueError("A reply already exists for this review")
    reply = CoachReply(
        review_id=review.id,
        instructor_id=instructor.id,
        body=body,
    )
    db.session.add(reply)
    db.session.commit()
    log_action(
        action='review.reply',
        resource_type='coach_reply',
        resource_id=reply.id,
        user_id=instructor.id,
        new_value={'review_id': review.id},
    )
    return reply


def update_coach_reply(reply: CoachReply, instructor: User, body: str) -> CoachReply:
    if reply.instructor_id != instructor.id:
        raise PermissionError("Cannot edit another instructor's reply")
    reply.body = body
    reply.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return reply


def create_training_class(data: dict, instructor: User) -> TrainingClass:
    from datetime import date as _date
    from app.utils.validators import validate_string
    title = validate_string(data.get('title'), 'Title', min_len=3, max_len=200)
    description = data.get('description', '')

    class_date = data.get('class_date')
    if class_date is None:
        raise ValueError('Class date is required')
    if class_date is not None and not isinstance(class_date, _date):
        raise ValueError('class_date must be a date object')

    location = data.get('location')
    if not location or not str(location).strip():
        raise ValueError('Location is required')

    tc = TrainingClass(
        title=title,
        description=description,
        instructor_id=instructor.id,
        org_unit_id=data['org_unit_id'],
        class_date=class_date,
        location=str(location).strip(),
        max_attendees=int(data.get('max_attendees', 30)),
        is_active=True,
    )
    db.session.add(tc)
    db.session.commit()
    log_action(
        action='class.create',
        resource_type='training_class',
        resource_id=tc.id,
        user_id=instructor.id,
    )
    return tc


def register_for_class(class_id: int, user: User) -> ClassAttendee:
    tc = TrainingClass.query.get_or_404(class_id)
    from app.services.permission_service import user_accessible_org_ids
    accessible_orgs = user_accessible_org_ids(user)
    if not accessible_orgs:
        raise PermissionError("You do not have access to this class")
    if tc.org_unit_id not in accessible_orgs:
        raise PermissionError("You do not have access to this class")
    if not tc.is_active:
        raise ValueError("This class is no longer active")
    count = ClassAttendee.query.filter_by(class_id=class_id).count()
    if count >= tc.max_attendees:
        raise ValueError("This class is full")
    existing = ClassAttendee.query.filter_by(class_id=class_id, user_id=user.id).first()
    if existing:
        raise ValueError("You are already registered for this class")
    att = ClassAttendee(class_id=class_id, user_id=user.id)
    db.session.add(att)
    db.session.commit()
    return att


def mark_attendance(class_id: int, user_ids: list[int], instructor: User):
    tc = TrainingClass.query.get_or_404(class_id)
    if tc.instructor_id != instructor.id:
        raise PermissionError("Only the instructor can mark attendance")
    for uid in user_ids:
        att = ClassAttendee.query.filter_by(class_id=class_id, user_id=uid).first()
        if att:
            att.attended = True
    db.session.commit()


def format_reviewer_name(user: User, display_mode: str) -> str:
    if display_mode == 'full_name':
        return user.full_name or user.username
    elif display_mode == 'initials':
        name = user.full_name or user.username
        parts = name.split()
        return '.'.join(p[0].upper() for p in parts if p) + '.'
    else:
        return 'Anonymous Reviewer'


def get_reviews_for_class(class_id: int, display_mode: str = 'anonymous', visible_only: bool = True):
    query = ClassReview.query.filter_by(class_id=class_id)
    if visible_only:
        query = query.filter_by(is_visible=True)
    reviews = query.order_by(ClassReview.created_at.desc()).all()
    result = []
    for r in reviews:
        reviewer = db.session.get(User, r.reviewer_id)
        data = r.to_dict()
        data['reviewer_display'] = format_reviewer_name(reviewer, display_mode)
        data['coach_reply'] = r.coach_reply.to_dict() if r.coach_reply else None
        result.append(data)
    if reviews:
        ratings = [r.rating for r in reviews]
        avg = round(sum(ratings) / len(ratings), 1)
        dist = {i: ratings.count(i) for i in range(1, 6)}
    else:
        avg = 0
        dist = {i: 0 for i in range(1, 6)}
    return {'reviews': result, 'average_rating': avg, 'rating_distribution': dist, 'total': len(reviews)}
