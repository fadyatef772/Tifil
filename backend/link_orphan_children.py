#!/usr/bin/env python3
"""One-time migration: link orphaned (parent_id=NULL) children to a parent account.

After deploying parent authentication, any children created before auth
existed will have parent_id=NULL and are unreachable.  This script assigns
them to a parent account so they become accessible again.

Usage:
    python link_orphan_children.py                          # interactive prompt
    python link_orphan_children.py --email user@example.com # use existing parent
    python link_orphan_children.py --email user@example.com --name "User Name"
                                                            # create if missing

The script is idempotent: running it twice does nothing the second time
(only touches children WHERE parent_id IS NULL).

Run from the backend/ directory:
    cd backend
    python link_orphan_children.py --email fady@example.com
"""

import argparse
import os
import sys

# Must be set before importing the app.
os.environ.setdefault("TIFL_SECRET_KEY", "migration-run-only-not-for-production")

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal, Base, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.domain.models import Child, Parent  # noqa: E402


def _ensure_parent_columns():
    """Add parent_id column to children and create parents table if needed.
    SQLite: create_all cannot ALTER TABLE, so we do it with raw SQL."""
    Base.metadata.create_all(engine)
    # Check if parent_id column exists on children.
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info(children)")).fetchall()
        col_names = [r[1] for r in cols]
        if "parent_id" not in col_names:
            conn.execute(text(
                "ALTER TABLE children "
                "ADD COLUMN parent_id INTEGER REFERENCES parents(id)"
            ))
            conn.commit()
            print("Added parent_id column to children table.")
        else:
            print("parent_id column already exists.")


def main():
    _ensure_parent_columns()

    parser = argparse.ArgumentParser(description="Link orphaned children to a parent.")
    parser.add_argument("--email", help="Parent email (will create if missing)")
    parser.add_argument("--name", default="Migrated Parent", help="Parent name (for creation)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Find orphaned children.
        orphans = db.query(Child).filter(Child.parent_id.is_(None)).all()
        if not orphans:
            print("No orphaned children found (all children already linked). Nothing to do.")
            return

        print(f"Found {len(orphans)} orphaned child(ren):")
        for c in orphans:
            print(f"  - #{c.id} {c.name} (preferred_language={c.preferred_language})")

        # Resolve or create the parent.
        email = args.email
        if not email:
            email = input("\nParent email to assign them to: ").strip()
            if not email:
                print("No email provided. Aborting.")
                sys.exit(1)

        parent = db.query(Parent).filter(Parent.email == email).first()
        if parent is None:
            name = args.name
            if not args.name and not args.email:
                name = input("Parent name [Migrated Parent]: ").strip() or "Migrated Parent"
            parent = Parent(
                email=email,
                password_hash=hash_password("set-a-real-password-now"),
                name=name,
            )
            db.add(parent)
            db.commit()
            db.refresh(parent)
            print(f"\nCreated new parent #{parent.id}: {parent.email} ({parent.name})")
            print("  *** IMPORTANT: have them change the password via the app ***")
        else:
            print(f"\nUsing existing parent #{parent.id}: {parent.email} ({parent.name})")

        # Link orphans.
        linked = 0
        for c in orphans:
            c.parent_id = parent.id
            linked += 1
            print(f"  Linked: #{c.id} {c.name} -> parent #{parent.id} {parent.email}")

        db.commit()
        print(f"\nDone. {linked} child(ren) linked to {parent.email}.")
        print("Running this script again will find nothing to do.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
