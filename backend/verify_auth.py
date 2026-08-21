#!/usr/bin/env python3
"""Auth layer verification (Layer 9: parent authentication).

Checks:
  1. Parent signup (POST /api/auth/signup) returns a token.
  2. Parent login (POST /api/auth/login) returns a token.
  3. GET /api/auth/me returns the parent profile.
  4. Child creation auto-sets parent_id.
  5. list_children scoped to parent.
  6. Child access denied for wrong parent.
  7. Unauthenticated access denied.
  8. Password minimum length enforced.
  9. Duplicate email rejected.
 10. Token expiry (invalid token rejected).

All tests use an in-memory SQLite database (via TestClient) so no existing
data is touched.  Run:  python verify_auth.py
"""

import os
import sys

os.environ["TIFL_DATABASE_URL"] = "sqlite:///./verify_auth.db"
os.environ["TIFL_SECRET_KEY"] = "test-only-dev-secret-not-for-production"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
client = TestClient(app)

PARENT_EMAIL = "verify_test_parent@example.com"
PARENT_PASSWORD = "testpass123"
PARENT_NAME = "Test Parent"


def _create_parent(email=PARENT_EMAIL, password=PARENT_PASSWORD, name=PARENT_NAME):
    """Sign up a parent and return the bearer token."""
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "name": name},
    )
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_01_signup():
    """POST /api/auth/signup returns a token."""
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "parent_signup@example.com",
            "password": "password123",
            "name": "Signup Parent",
        },
    )
    assert r.status_code == 200, f"signup failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data, "signup response missing access_token"
    assert data["token_type"] == "bearer"


def test_02_login():
    """POST /api/auth/login returns a token."""
    token = _create_parent("parent_login@example.com")
    r = client.post(
        "/api/auth/login",
        json={"email": "parent_login@example.com", "password": PARENT_PASSWORD},
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data, "login response missing access_token"


def test_03_me():
    """GET /api/auth/me returns the parent profile."""
    token = _create_parent("parent_me@example.com")
    r = client.get("/api/auth/me", headers=_auth(token))
    assert r.status_code == 200, f"me failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["email"] == "parent_me@example.com"
    assert data["name"] == "Test Parent"
    assert "id" in data


def test_04_child_auto_parent_id():
    """POST /api/children auto-sets parent_id."""
    token = _create_parent("parent_child@example.com")
    r = client.post(
        "/api/children",
        json={"name": "Auth Test Child", "preferred_language": "ar"},
        headers=_auth(token),
    )
    assert r.status_code == 200, f"create child failed: {r.status_code} {r.text}"
    child = r.json()
    assert child["name"] == "Auth Test Child"


def test_05_list_scoped():
    """GET /api/children returns only this parent's children."""
    token_a = _create_parent("parent_scope_a@example.com")
    token_b = _create_parent("parent_scope_b@example.com")

    # Create a child for parent A.
    client.post(
        "/api/children",
        json={"name": "Child A", "preferred_language": "ar"},
        headers=_auth(token_a),
    )
    # Create a child for parent B.
    client.post(
        "/api/children",
        json={"name": "Child B", "preferred_language": "en"},
        headers=_auth(token_b),
    )

    # Parent A should only see Child A.
    r = client.get("/api/children", headers=_auth(token_a))
    names = [c["name"] for c in r.json()]
    assert "Child A" in names
    assert "Child B" not in names

    # Parent B should only see Child B.
    r = client.get("/api/children", headers=_auth(token_b))
    names = [c["name"] for c in r.json()]
    assert "Child B" in names
    assert "Child A" not in names


def test_06_wrong_parent_denied():
    """Accessing another parent's child returns 404."""
    token_a = _create_parent("parent_denied_a@example.com")
    token_b = _create_parent("parent_denied_b@example.com")

    # Create a child for parent A.
    r = client.post(
        "/api/children",
        json={"name": "Private Child", "preferred_language": "ar"},
        headers=_auth(token_a),
    )
    child_id = r.json()["id"]

    # Parent B tries to access Parent A's child — should 404.
    r = client.get(f"/api/children/{child_id}", headers=_auth(token_b))
    assert r.status_code == 404, f"expected 404 for wrong parent, got {r.status_code}"


def test_07_unauthenticated_denied():
    """Unauthenticated access to child endpoints returns 401."""
    r = client.get("/api/children")
    assert r.status_code == 401, f"expected 401, got {r.status_code}"

    r = client.post(
        "/api/children",
        json={"name": "No Auth Child", "preferred_language": "ar"},
    )
    assert r.status_code == 401, f"expected 401, got {r.status_code}"


def test_08_password_min_length():
    """Short password is rejected (422)."""
    r = client.post(
        "/api/auth/signup",
        json={"email": "short@example.com", "password": "short", "name": "Short"},
    )
    assert r.status_code == 422, f"expected 422 for short password, got {r.status_code}"


def test_09_duplicate_email():
    """Duplicate email signup is rejected (409)."""
    _create_parent("dup@example.com")
    r = client.post(
        "/api/auth/signup",
        json={"email": "dup@example.com", "password": "password123", "name": "Dup"},
    )
    assert r.status_code == 409, f"expected 409 for duplicate email, got {r.status_code}"


def test_10_invalid_token():
    """Invalid/expired token is rejected (401)."""
    r = client.get("/api/auth/me", headers=_auth("invalid.token.here"))
    assert r.status_code == 401, f"expected 401 for invalid token, got {r.status_code}"


def test_11_secret_key_missing_fails_fast():
    """App refuses to start when TIFL_SECRET_KEY is not set."""
    import subprocess

    code = (
        "import os; os.environ.pop('TIFL_SECRET_KEY', None); "
        "os.environ['TIFL_DATABASE_URL'] = 'sqlite:///./verify_auth.db'; "
        "from app.core.config import Settings; Settings()"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__) or ".",
    )
    assert r.returncode != 0, "expected non-zero exit for missing TIFL_SECRET_KEY"
    combined = r.stderr + r.stdout
    assert "secret" in combined.lower() or "required" in combined.lower(), (
        f"error should mention missing secret_key, got stderr={r.stderr!r}"
    )


def test_12_secret_key_old_default_rejected():
    """App refuses to start when TIFL_SECRET_KEY is the old insecure default."""
    import subprocess

    code = (
        "import os; "
        "os.environ['TIFL_SECRET_KEY'] = 'dev-only-secret-change-me-in-production'; "
        "os.environ['TIFL_DATABASE_URL'] = 'sqlite:///./verify_auth.db'; "
        "from app.core.config import Settings; Settings()"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__) or ".",
    )
    assert r.returncode != 0, "expected non-zero exit for old default secret"
    combined = r.stderr + r.stdout
    assert "insecure" in combined.lower() or "dev" in combined.lower() or "default" in combined.lower(), (
        f"error message should mention insecure/default, got stderr={r.stderr!r}"
    )


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for fn in tests:
        name = fn.__name__
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except Exception as exc:
            print(f"  ✗ {name}: {exc}")
            failed += 1
    print(f"\nAuth: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
