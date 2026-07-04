"""
config.py - Environment-driven configuration.

PUBLIC_BASE_URL matters because the Raspberry Pi may reach this server
over a different hostname than what Flask sees on a single request
(e.g. behind a reverse proxy, or a domain vs an internal port). Set it
explicitly in production rather than relying on request.host_url.

API_KEY is the shared secret the Raspberry Pi uses to call the /api/*
endpoints (create exam, pull registrations). Generate one with:
    python3 -c "import secrets; print(secrets.token_urlsafe(32))"
and put the same value in both this server's env and the Pi's config.

ADMIN_PASSWORD gates the human /admin pages (exam creation, viewing
who has registered). This is separate from API_KEY, which is for the
Pi calling in as a machine, not a person logging in.
"""
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-in-production")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://exam-qr-registration.onrender.com").rstrip("/")  # e.g. https://examreg.yourdomain.com
API_KEY = os.environ.get("API_KEY", "dev-api-key-change-this")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")


def public_base_url(request) -> str:
    """Prefer the configured public URL; fall back to the request's own host."""
    return PUBLIC_BASE_URL or request.host_url.rstrip("/")
