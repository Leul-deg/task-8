from datetime import date as date_type
from flask import Blueprint, render_template, request, redirect, flash, abort, current_app
from flask_login import login_required, current_user
from app.models.training import TrainingClass, ClassAttendee, ClassReview
from app.models.organization import OrgUnit
from app.services.permission_service import has_permission, user_accessible_org_ids
from app.utils.decorators import require_permission
from app.services.review_service import (
    create_training_class, register_for_class, mark_attendance,
    create_review, add_coach_reply, get_reviews_for_class,
)

class_pages_bp = Blueprint('class_pages', __name__, url_prefix='/classes')


@class_pages_bp.route('')
@login_required
def index():
    search = request.args.get('search', '')
    accessible = user_accessible_org_ids(current_user)
    query = TrainingClass.query.filter(TrainingClass.org_unit_id.in_(accessible))
    if search:
        query = query.filter(TrainingClass.title.ilike(f'%{search}%'))
    classes = query.order_by(TrainingClass.class_date.desc()).all()
    if request.headers.get('HX-Request'):
        return render_template('classes/partials/class_list.html', classes=classes)
    return render_template('classes/index.html', classes=classes, search=search)


@class_pages_bp.route('/new')
@login_required
@require_permission('class.create')
def new():
    orgs = OrgUnit.query.filter_by(is_active=True).all()
    return render_template('classes/form.html', org_units=orgs)


@class_pages_bp.route('', methods=['POST'])
@login_required
@require_permission('class.create')
def create():
    raw_date = request.form.get('class_date', '').strip()
    try:
        parsed_date = date_type.fromisoformat(raw_date) if raw_date else None
    except ValueError:
        flash('Invalid date format. Use YYYY-MM-DD.', 'error')
        return redirect('/classes/new')

    raw_org = request.form.get('org_unit_id', '').strip()
    if not raw_org or not raw_org.isdigit():
        flash('Organization unit is required.', 'error')
        return redirect('/classes/new')

    org_id = int(raw_org)
    if org_id not in user_accessible_org_ids(current_user):
        abort(403)

    data = {
        'title': request.form.get('title'),
        'description': request.form.get('description'),
        'class_date': parsed_date,
        'location': request.form.get('location'),
        'max_attendees': request.form.get('max_attendees', 30),
        'org_unit_id': org_id,
    }
    try:
        tc = create_training_class(data, current_user)
        flash('Class created', 'success')
        return redirect(f'/classes/{tc.id}')
    except (ValueError, KeyError) as e:
        flash(str(e), 'error')
        return redirect('/classes/new')
    except Exception:
        from app.extensions import db
        db.session.rollback()
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect('/classes/new')


@class_pages_bp.route('/<int:class_id>')
@login_required
def detail(class_id):
    tc = TrainingClass.query.get_or_404(class_id)
    if tc.org_unit_id not in user_accessible_org_ids(current_user):
        abort(403)
    attendees = ClassAttendee.query.filter_by(class_id=class_id).all()
    is_registered = any(a.user_id == current_user.id for a in attendees)
    is_instructor = (tc.instructor_id == current_user.id)
    has_reviewed = ClassReview.query.filter_by(class_id=class_id, reviewer_id=current_user.id).first() is not None
    can_review = is_registered and any(a.user_id == current_user.id and a.attended for a in attendees) and not has_reviewed
    display_mode = tc.org_unit.reviewer_display_mode if tc.org_unit else current_app.config.get('REVIEWER_DISPLAY_MODE', 'anonymous')
    review_data = get_reviews_for_class(class_id, display_mode=display_mode)
    return render_template('classes/detail.html', tc=tc, attendees=attendees,
                           is_registered=is_registered, is_instructor=is_instructor,
                           can_review=can_review, **review_data)


@class_pages_bp.route('/<int:class_id>/register', methods=['POST'])
@login_required
def register(class_id):
    try:
        register_for_class(class_id, current_user)
        flash('Registered successfully', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(f'/classes/{class_id}')


@class_pages_bp.route('/<int:class_id>/attendance', methods=['POST'])
@login_required
def attendance(class_id):
    user_ids = [int(uid) for uid in request.form.getlist('attended_users')]
    try:
        mark_attendance(class_id, user_ids, current_user)
        flash('Attendance updated', 'success')
    except PermissionError as e:
        flash(str(e), 'error')
    return redirect(f'/classes/{class_id}')


@class_pages_bp.route('/<int:class_id>/reviews', methods=['POST'])
@login_required
def submit_review(class_id):
    data = {
        'rating': int(request.form.get('rating', 0)),
        'tags': request.form.getlist('tags'),
        'comment': request.form.get('comment'),
    }
    try:
        create_review(class_id, current_user, data)
        flash('Review submitted', 'success')
    except (ValueError, PermissionError) as e:
        flash(str(e), 'error')
    return redirect(f'/classes/{class_id}')


@class_pages_bp.route('/<int:class_id>/reviews/<int:review_id>/reply', methods=['POST'])
@login_required
def reply_to_review(class_id, review_id):
    if not has_permission(current_user, 'review.reply'):
        abort(403)
    tc = TrainingClass.query.get_or_404(class_id)
    if tc.instructor_id != current_user.id:
        abort(403)
    review = ClassReview.query.get_or_404(review_id)
    if review.class_id != class_id:
        abort(404)
    body = request.form.get('body', '')
    try:
        add_coach_reply(review, current_user, body)
        flash('Reply posted', 'success')
    except (ValueError, PermissionError) as e:
        flash(str(e), 'error')
    return redirect(f'/classes/{class_id}')
