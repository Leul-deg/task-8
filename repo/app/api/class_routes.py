from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models.training import TrainingClass
from app.services.permission_service import user_accessible_org_ids
from app.api.middleware import verify_hmac_signature

class_bp = Blueprint('classes', __name__, url_prefix='/api/classes')


@class_bp.route('', methods=['GET'])
@verify_hmac_signature
@login_required
def list_classes():
    search = request.args.get('search', '')
    accessible = user_accessible_org_ids(current_user)
    query = TrainingClass.query.filter(TrainingClass.org_unit_id.in_(accessible))
    if search:
        query = query.filter(TrainingClass.title.ilike(f'%{search}%'))
    classes = query.order_by(TrainingClass.class_date.desc()).all()
    if request.headers.get('HX-Request'):
        return render_template('classes/partials/class_list.html', classes=classes)
    return jsonify([c.to_dict() for c in classes]), 200
