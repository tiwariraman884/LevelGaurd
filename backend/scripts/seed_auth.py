from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User


ADMIN_EMAIL = "admin@labelguard.local"
ADMIN_PASSWORD = "Admin@LabelGuard2026"

REQUIRED_ROLES = {
    "district_collector": "District-level escalation authority",
    "state_admin": "State-level escalation authority",
    "national_admin": "National-level escalation authority",
}


def seed_roles_and_admin() -> None:
    db = SessionLocal()

    try:
        # Create roles if they do not exist.
        admin_role = db.scalar(
            select(Role).where(Role.name == "admin")
        )

        if admin_role is None:
            admin_role = Role(
                name="admin",
                description="System administrator",
            )
            db.add(admin_role)
            db.flush()

        inspector_role = db.scalar(
            select(Role).where(Role.name == "inspector")
        )

        if inspector_role is None:
            inspector_role = Role(
                name="inspector",
                description="Legal Metrology inspection officer",
            )
            db.add(inspector_role)
            db.flush()

        auditor_role = db.scalar(
            select(Role).where(Role.name == "auditor")
        )

        if auditor_role is None:
            auditor_role = Role(
                name="auditor",
                description="Read-only inspection auditor",
            )
            db.add(auditor_role)
            db.flush()

        for role_name, description in REQUIRED_ROLES.items():
            role = db.scalar(
                select(Role).where(Role.name == role_name)
            )
            if role is None:
                db.add(
                    Role(
                        name=role_name,
                        description=description,
                    )
                )
                db.flush()
                print(f"Role created: {role_name}")
            else:
                print(f"Role already exists: {role_name}")

        # Create standard accounts for all roles
        SEED_USERS = [
            {
                "email": "admin@labelguard.local",
                "aliases": ["admin@labelguard.gov.in"],
                "role_name": "admin",
                "full_name": "National Administrator",
                "passwords": ["Admin@LabelGuard2026", "demo"],
            },
            {
                "email": "inspector@labelguard.gov.in",
                "aliases": ["inspector@labelguard.local"],
                "role_name": "inspector",
                "full_name": "Field Inspector",
                "passwords": ["Inspector@123", "demo"],
            },
            {
                "email": "controller@labelguard.gov.in",
                "aliases": ["district@labelguard.gov.in"],
                "role_name": "district_collector",
                "full_name": "District Controller",
                "passwords": ["District@123", "demo"],
            },
            {
                "email": "state@labelguard.gov.in",
                "aliases": ["state_admin@labelguard.gov.in"],
                "role_name": "state_admin",
                "full_name": "State Administrator",
                "passwords": ["State@123", "demo"],
            },
            {
                "email": "national@labelguard.gov.in",
                "aliases": ["national_admin@labelguard.gov.in"],
                "role_name": "national_admin",
                "full_name": "National Administrator",
                "passwords": ["National@123", "demo"],
            },
            {
                "email": "auditor@labelguard.gov.in",
                "aliases": ["auditor@labelguard.local"],
                "role_name": "auditor",
                "full_name": "Compliance Auditor",
                "passwords": ["Auditor@123", "demo"],
            },
        ]

        roles_by_name = {
            r.name: r for r in db.scalars(select(Role)).all()
        }

        for user_data in SEED_USERS:
            role = roles_by_name.get(user_data["role_name"])
            if not role:
                continue

            all_emails = [user_data["email"]] + user_data.get("aliases", [])
            for email in all_emails:
                existing = db.scalar(select(User).where(User.email == email))
                if existing is None:
                    u = User(
                        role_id=role.id,
                        full_name=user_data["full_name"],
                        email=email,
                        password_hash=hash_password(user_data["passwords"][0]),
                        is_active=True,
                    )
                    db.add(u)
                    print(f"Created user: {email} ({user_data['role_name']})")
                else:
                    # Update password to standard password
                    existing.password_hash = hash_password(user_data["passwords"][0])
                    existing.role_id = role.id
                    existing.is_active = True
                    print(f"Updated user: {email} ({user_data['role_name']})")

        db.commit()

        print("Roles and user seed completed.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_roles_and_admin()

