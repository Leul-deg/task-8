def mask_field(value: str, mask_type: str = 'partial') -> str:
    if not value:
        return ''
    if mask_type == 'full':
        return '****'
    if mask_type == 'initials':
        parts = value.split()
        return '.'.join(p[0].upper() for p in parts if p) + '.' if parts else '****'
    if mask_type == 'partial':
        if len(value) <= 4:
            return value[0] + '***'
        return value[:2] + '*' * (len(value) - 4) + value[-2:]
    return value


def get_mask_type_for_role(viewer_roles: list, field_type: str = 'email') -> str:
    role_names = [r.name for r in viewer_roles]
    if 'org_admin' in role_names or 'property_manager' in role_names:
        return 'none'
    if field_type == 'email':
        return 'partial'
    if field_type == 'name':
        return 'initials'
    if field_type == 'address':
        return 'partial'
    return 'partial'
