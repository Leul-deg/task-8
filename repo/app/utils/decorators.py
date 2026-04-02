import functools
from flask import jsonify, request, g
from flask_login import current_user


def require_permission(codename: str, org_unit_param: str | None = None):
    """Decorator that requires the current user to have a specific permission.

    If org_unit_param is given, the org unit id is extracted from URL kwargs or
    query string and passed to has_permission() for scope checking.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            from app.services.permission_service import has_permission
            org_unit_id = None
            if org_unit_param:
                org_unit_id = kwargs.get(org_unit_param) or request.args.get(org_unit_param, type=int)
            if not has_permission(current_user, codename, org_unit_id=org_unit_id):
                return jsonify({'error': 'Permission denied'}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


def require_role(role_name: str):
    """Decorator that requires the current user to have a specific role."""
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            if not any(r.name == role_name for r in current_user.roles):
                return jsonify({'error': 'Insufficient role'}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


def audit_action(action: str, resource_type: str):
    """Decorator that logs an audit entry after the wrapped function executes."""
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            result = f(*args, **kwargs)
            try:
                from app.services.audit_service import log_action
                resource_id = getattr(g, 'audited_resource_id', None)
                old_value = getattr(g, 'audited_old_value', None)
                new_value = getattr(g, 'audited_new_value', None)
                user_id = current_user.id if current_user.is_authenticated else None
                log_action(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    old_value=old_value,
                    new_value=new_value,
                    ip_address=request.remote_addr,
                )
            except Exception:
                from flask import current_app
                current_app.logger.exception('audit_action logging failed for action=%s', action)
            return result
        return wrapped
    return decorator
