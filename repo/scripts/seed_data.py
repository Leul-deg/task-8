import sys
import os
import secrets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def seed():
    from app.extensions import db
    from app.models.user import User, Role, Permission
    from app.models.organization import OrgUnit, UserOrgUnit
    from app.utils.constants import DEFAULT_ROLES, DEFAULT_PERMISSIONS, OrgUnitLevel
    env_name = os.environ.get('APP_CONFIG_NAME') or os.environ.get('FLASK_ENV', 'development')
    allow_default_bootstrap_users = os.environ.get('ALLOW_DEFAULT_BOOTSTRAP_USERS') == '1' or env_name != 'production'
    bootstrap_admin_password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
    bootstrap_staff_password = os.environ.get('BOOTSTRAP_STAFF_PASSWORD')

    # Seed permissions
    perms = {}
    for pdata in DEFAULT_PERMISSIONS:
        p = Permission.query.filter_by(codename=pdata['codename']).first()
        if not p:
            p = Permission(**pdata)
            db.session.add(p)
        perms[pdata['codename']] = p
    db.session.flush()

    # Seed roles
    roles = {}
    for rdata in DEFAULT_ROLES:
        r = Role.query.filter_by(name=rdata['name']).first()
        if not r:
            r = Role(**rdata)
            db.session.add(r)
        roles[rdata['name']] = r
    db.session.flush()

    # org_admin gets all permissions
    org_admin = roles['org_admin']
    existing_admin_perms = {p.codename for p in org_admin.permissions}
    for perm in perms.values():
        if perm.codename not in existing_admin_perms:
            org_admin.permissions.append(perm)

    # property_manager gets listing permissions
    pm = roles['property_manager']
    existing_pm_perms = {p.codename for p in pm.permissions}
    for codename in ['listing.create', 'listing.edit', 'listing.publish', 'listing.delete', 'listing.lock']:
        if codename in perms and codename not in existing_pm_perms:
            pm.permissions.append(perms[codename])

    # instructor gets class.create and review.reply
    instr = roles['instructor']
    existing_instr_perms = {p.codename for p in instr.permissions}
    for codename in ['class.create', 'review.reply']:
        if codename in perms and codename not in existing_instr_perms:
            instr.permissions.append(perms[codename])

    # content_moderator gets review.moderate
    mod = roles['content_moderator']
    existing_mod_perms = {p.codename for p in mod.permissions}
    for codename in ['review.moderate']:
        if codename in perms and codename not in existing_mod_perms:
            mod.permissions.append(perms[codename])

    # staff gets basic permissions
    staff_role = roles['staff']
    existing_staff_perms = {p.codename for p in staff_role.permissions}
    for codename in ['review.create', 'listing.create']:
        if codename in perms and codename not in existing_staff_perms:
            staff_role.permissions.append(perms[codename])

    db.session.flush()

    # Create org hierarchy: Main Campus → College of Medicine → Internal Medicine → Cardiology
    campus = OrgUnit.query.filter_by(code='MAIN').first()
    if not campus:
        campus = OrgUnit(name='Main Campus', code='MAIN', level=OrgUnitLevel.CAMPUS.value)
        db.session.add(campus)
        db.session.flush()

    college = OrgUnit.query.filter_by(code='COM').first()
    if not college:
        college = OrgUnit(
            name='College of Medicine', code='COM',
            level=OrgUnitLevel.COLLEGE.value, parent_id=campus.id,
        )
        db.session.add(college)
        db.session.flush()

    dept = OrgUnit.query.filter_by(code='IM').first()
    if not dept:
        dept = OrgUnit(
            name='Internal Medicine', code='IM',
            level=OrgUnitLevel.DEPARTMENT.value, parent_id=college.id,
        )
        db.session.add(dept)
        db.session.flush()

    section = OrgUnit.query.filter_by(code='CARD').first()
    if not section:
        section = OrgUnit(
            name='Cardiology', code='CARD',
            level=OrgUnitLevel.SECTION.value, parent_id=dept.id,
        )
        db.session.add(section)
        db.session.flush()

    if allow_default_bootstrap_users:
        # Admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            generated_admin_password = bootstrap_admin_password or secrets.token_urlsafe(12)
            admin = User(
                username='admin',
                email='admin@clinical.local',
                full_name='System Administrator',
                display_preference='full_name',
            )
            admin.set_password(generated_admin_password)
            db.session.add(admin)
            db.session.flush()
            admin.roles.append(roles['org_admin'])
            db.session.add(UserOrgUnit(user_id=admin.id, org_unit_id=campus.id, is_primary=True))
            print(f'Bootstrap admin created: username=admin password={generated_admin_password}')

        # Staff user
        staff_user = User.query.filter_by(username='staff').first()
        if not staff_user:
            generated_staff_password = bootstrap_staff_password or secrets.token_urlsafe(12)
            staff_user = User(
                username='staff',
                email='staff@clinical.local',
                full_name='Staff Member',
                display_preference='anonymous',
            )
            staff_user.set_password(generated_staff_password)
            db.session.add(staff_user)
            db.session.flush()
            staff_user.roles.append(roles['staff'])
            db.session.add(UserOrgUnit(user_id=staff_user.id, org_unit_id=campus.id, is_primary=True))
            print(f'Bootstrap staff created: username=staff password={generated_staff_password}')

    db.session.commit()
    print('Seeding complete.')


if __name__ == '__main__':
    from app import create_app
    from app import _create_fts_table
    from app.extensions import db

    env = os.environ.get('FLASK_ENV', 'development')
    app = create_app(env)
    with app.app_context():
        db.create_all()
        _create_fts_table(db)
        seed()
