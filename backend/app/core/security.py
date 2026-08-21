"""Password hashing and token management.

Passwords are hashed with passlib+bcrypt (NEVER stored or logged in plaintext).
Tokens are HMAC-signed base64 (no JWT library needed — the simplest secure
option for a stateless bearer token).

Token payload: {"parent_id": int, "exp": int (unix seconds)}
Token lifetime: configurable via TIFL_SESSION_EXPIRY_DAYS (default 30 days).
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from passlib.context import CryptContext

from app.core.config import settings

# ── Password hashing ──────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt. The hash includes its own salt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


# ── Token signing ─────────────────────────────────────────────────────────
# HMAC-SHA256 signing with the app's secret (env var TIFL_SECRET_KEY).
# The app refuses to start without a real key — see config.py.


def _get_signing_key() -> bytes:
    """Derive a 32-byte signing key from the app's secret."""
    secret = settings.secret_key.encode("utf-8")
    return hashlib.sha256(secret).digest()


def _sign(payload_bytes: bytes) -> str:
    """Create an HMAC-SHA256 signature and append it to the payload."""
    key = _get_signing_key()
    sig = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    return sig


def create_token(parent_id: int) -> str:
    """Create a signed bearer token for a parent."""
    exp = int(time.time()) + (settings.session_expiry_days * 86400)
    payload = json.dumps({"parent_id": parent_id, "exp": exp}).encode("utf-8")
    sig = _sign(payload)
    token_data = base64.urlsafe_b64encode(payload).decode("utf-8")
    return f"{token_data}.{sig}"


def decode_token(token: str) -> Optional[int]:
    """Decode and verify a bearer token. Returns the parent_id or None if
    invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        token_data, sig = parts
        payload = base64.urlsafe_b64decode(token_data + "==")
        # Verify signature
        expected_sig = _sign(payload)
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # Parse and check expiry
        data = json.loads(payload)
        if data.get("exp", 0) < time.time():
            return None
        return data.get("parent_id")
    except Exception:
        return None
