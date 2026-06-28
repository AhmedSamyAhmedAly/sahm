"""Create the initial set of accounts on whatever DB DATABASE_URL points to.

Generates a secure temp password per user, sets the role, upserts by email,
and prints the credentials to share. Re-running resets the password.

    DATABASE_URL=<neon url>  python scripts/create_accounts.py
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models import User  # noqa: E402

# (first, last, role) — role is admin | member. "super admin" == admin; the
# pinned ADMIN_EMAIL (ahmed.samy@sahm.app) is the primary/super admin.
PEOPLE = [
    ("Ahmed", "Samy", "admin"),
    ("Khaled", "Elnagdy", "admin"),
    ("Nouran", "Mosaad", "member"),
    ("Nancy", "Mossad", "member"),
    ("Abdelrahman", "Marmoush", "member"),
]
DOMAIN = "sahm.app"


def main() -> None:
    init_db()
    rows = []
    with SessionLocal() as db:
        for first, last, role in PEOPLE:
            email = f"{first}.{last}@{DOMAIN}".lower()
            password = secrets.token_urlsafe(9)  # ~12 chars, secure temp
            u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if u is None:
                u = User(email=email)
                db.add(u)
            u.hashed_password = hash_password(password)
            u.role = role
            u.is_active = True
            rows.append((f"{first} {last}", email, role, password))
        db.commit()

    print("\n=== ACCOUNTS CREATED (share these; users can change later) ===\n")
    print(f"{'Name':<22} {'Email':<32} {'Role':<8} Temp password")
    print("-" * 84)
    for name, email, role, pw in rows:
        print(f"{name:<22} {email:<32} {role:<8} {pw}")
    print()


if __name__ == "__main__":
    main()
