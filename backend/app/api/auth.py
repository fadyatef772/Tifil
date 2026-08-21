"""Parent authentication routes.

Only parents have credentials (email + password). Children NEVER type a
password — they pick their avatar from the child-picker screen after the
parent is logged in.

Endpoints:
  POST /api/auth/signup  — register a new parent account
  POST /api/auth/login   — log in with email + password, returns a bearer token
  GET  /api/auth/me      — get the current parent's profile (requires auth)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domain.models import Parent
from app.domain.schemas import ParentCreate, ParentLogin, ParentOut, TokenOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Dependency ────────────────────────────────────────────────────────────
def get_current_parent(request: Request, db: Session = Depends(get_db)) -> Parent:
    """Extract and verify the bearer token from the Authorization header.
    Returns the Parent ORM object or raises 401."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:]  # strip "Bearer "
    parent_id = decode_token(token)
    if parent_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    parent = db.query(Parent).filter(Parent.id == parent_id).first()
    if parent is None:
        raise HTTPException(status_code=401, detail="Parent not found")
    return parent


# ── Routes ────────────────────────────────────────────────────────────────
@router.post("/signup", response_model=TokenOut)
def signup(body: ParentCreate, db: Session = Depends(get_db)):
    """Register a new parent account. Returns a bearer token."""
    existing = db.query(Parent).filter(Parent.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    parent = Parent(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)
    return TokenOut(access_token=create_token(parent.id))


@router.post("/login", response_model=TokenOut)
def login(body: ParentLogin, db: Session = Depends(get_db)):
    """Log in with email + password. Returns a bearer token."""
    parent = db.query(Parent).filter(Parent.email == body.email).first()
    if parent is None or not verify_password(body.password, parent.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenOut(access_token=create_token(parent.id))


@router.get("/me", response_model=ParentOut)
def me(parent: Parent = Depends(get_current_parent)):
    """Return the current parent's profile."""
    return parent
