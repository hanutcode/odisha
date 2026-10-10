"""Django settings for the IRIS team workspace.

Runs locally by default (http://localhost:8000). For a server, set
HCM_DEBUG=0, HCM_ALLOWED_HOSTS=your.domain and HCM_SECRET_KEY.
"""

import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # web/
PROJECT_ROOT = BASE_DIR.parent                              # iris-hidden-cm/
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "demo"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


def _secret_key() -> str:
    if os.environ.get("HCM_SECRET_KEY"):
        return os.environ["HCM_SECRET_KEY"]
    f = BASE_DIR / ".secret_key"
    if not f.exists():
        f.write_text(secrets.token_urlsafe(50))
        os.chmod(f, 0o600)
    return f.read_text().strip()


SECRET_KEY = _secret_key()
DEBUG = os.environ.get("HCM_DEBUG", "1") == "1"
# MOCK model outputs: local development only (INTEGRITY rule 5). Off whenever DEBUG is off.
HCM_ALLOW_MOCK = os.environ.get("HCM_ALLOW_MOCK", "1" if DEBUG else "0") == "1"
ALLOWED_HOSTS = os.environ.get("HCM_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")

# NFHS-6 key: a file OUTSIDE the project, held by the engineer. Needed only
# for sealing uploads and for unsealing. Without it, those buttons are disabled.
HCM_SEAL_KEY = os.environ.get("HCM_SEAL_KEY", str(Path.home() / "nfhs6.key"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "workspace",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if os.environ.get("HCM_SERVE_STATIC") == "1":
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "iris_web.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "workspace.roles.context",
    ]},
}]
WSGI_APPLICATION = "iris_web.wsgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "workspace.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

FORCE_SCRIPT_NAME = os.environ.get("HCM_SCRIPT_NAME") or None
STATIC_URL = (FORCE_SCRIPT_NAME or "") + "/static/"
SESSION_COOKIE_PATH = (FORCE_SCRIPT_NAME or "") + "/"
CSRF_COOKIE_PATH = SESSION_COOKIE_PATH
SESSION_COOKIE_NAME = "hcm_sessionid"
CSRF_COOKIE_NAME = "hcm_csrftoken"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# NFHS district sheets: ~700 PDFs for all-India in one upload
DATA_UPLOAD_MAX_NUMBER_FILES = 1000
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# The map page is embedded in an iframe on the same site
X_FRAME_OPTIONS = "SAMEORIGIN"


# ---------------------------------------------------------------- production hardening
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 12 * 60 * 60          # sign in again after 12 hours
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Set HCM_HTTPS=1 once the site is served over HTTPS (Apache with a certificate).
if os.environ.get("HCM_HTTPS") == "1":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = int(os.environ.get("HCM_HSTS_SECONDS", "3600"))
    CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h and h not in ("localhost", "127.0.0.1", "[::1]")]

AUTH_PASSWORD_VALIDATORS += [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Errors to the container log (docker logs iris-cm); no secrets are logged.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {"django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False}},
}
