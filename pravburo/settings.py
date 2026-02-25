from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Сначала локальный .env, затем продовый .env.prod (если есть).
# override=False => если переменная уже задана в окружении (systemd), файл не перезатрёт.
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.prod", override=False)

def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}

def env_list(name: str, default=None, sep=","):
    v = os.getenv(name)
    if v is None:
        return default if default is not None else []
    return [x.strip() for x in v.split(sep) if x.strip()]

# ------------------------------------------------------------------
# CORE
# ------------------------------------------------------------------

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-key")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["*"])
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://prav-buro.ru")

# ------------------------------------------------------------------
# APPLICATIONS
# ------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "administration",
    "bitrix",
    "payments",
    "clients",
    "documents",
    "education_platform",
    "urlshorter",

    "corsheaders",
    "simple_history",
    "leadreport",
    "communications",
]

# ------------------------------------------------------------------
# MIDDLEWARE
# ------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "pravburo.urls"
WSGI_APPLICATION = "pravburo.wsgi.application"

# ------------------------------------------------------------------
# TEMPLATES
# ------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------

DB_ENGINE = os.getenv("DB_ENGINE", "postgres").lower()

if DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "bd"),
            "USER": os.getenv("DB_USER", "admin"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

# Дополнительные алиасы БД для модуля communications.
# Если отдельные БД не заданы, используем безопасный fallback:
# - sqlite: отдельные локальные файлы logs/archive
# - postgres: ту же БД, что и default
if DB_ENGINE == "sqlite":
    DATABASES["logs"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("LOGS_DB_NAME", str(BASE_DIR / "logs.sqlite3")),
    }
    DATABASES["archive"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("ARCHIVE_DB_NAME", str(BASE_DIR / "archive.sqlite3")),
    }
else:
    DATABASES["logs"] = {
        "ENGINE": os.getenv("LOGS_DB_ENGINE", DATABASES["default"]["ENGINE"]),
        "NAME": os.getenv("LOGS_DB_NAME", DATABASES["default"]["NAME"]),
        "USER": os.getenv("LOGS_DB_USER", DATABASES["default"]["USER"]),
        "PASSWORD": os.getenv("LOGS_DB_PASSWORD", DATABASES["default"]["PASSWORD"]),
        "HOST": os.getenv("LOGS_DB_HOST", DATABASES["default"]["HOST"]),
        "PORT": os.getenv("LOGS_DB_PORT", DATABASES["default"]["PORT"]),
    }
    DATABASES["archive"] = {
        "ENGINE": os.getenv("ARCHIVE_DB_ENGINE", DATABASES["default"]["ENGINE"]),
        "NAME": os.getenv("ARCHIVE_DB_NAME", DATABASES["default"]["NAME"]),
        "USER": os.getenv("ARCHIVE_DB_USER", DATABASES["default"]["USER"]),
        "PASSWORD": os.getenv("ARCHIVE_DB_PASSWORD", DATABASES["default"]["PASSWORD"]),
        "HOST": os.getenv("ARCHIVE_DB_HOST", DATABASES["default"]["HOST"]),
        "PORT": os.getenv("ARCHIVE_DB_PORT", DATABASES["default"]["PORT"]),
    }

DATABASE_ROUTERS = ["communications.db_router.CommunicationsRouter"]
COMMUNICATIONS_USE_CELERY = env_bool("COMMUNICATIONS_USE_CELERY", True)

# ------------------------------------------------------------------
# CELERY / REDIS
# ------------------------------------------------------------------

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "celery")

# ------------------------------------------------------------------
# AUTH / SECURITY
# ------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "login"

# ------------------------------------------------------------------
# I18N / TZ
# ------------------------------------------------------------------

LANGUAGE_CODE = os.getenv("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------
# STATIC / MEDIA
# ------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", DEBUG)
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)
CORS_ALLOW_ALL_METHODS = True

# ------------------------------------------------------------------
# ALFA
# ------------------------------------------------------------------

ALFA_API_URL_PROD = os.getenv("ALFA_API_URL_PROD", "")
ALFA_USER_PROD = os.getenv("ALFA_USER_PROD", "")
ALFA_PASS_PROD = os.getenv("ALFA_PASS_PROD", "")

# ------------------------------------------------------------------
# BITRIX
# ------------------------------------------------------------------

BITRIX_CLIENT_ID = os.getenv("BITRIX_CLIENT_ID", "")
BITRIX_CLIENT_SECRET = os.getenv("BITRIX_CLIENT_SECRET", "")
BITRIX_REDIRECT_URI = os.getenv("BITRIX_REDIRECT_URI", "http://localhost:8000/auth/bitrix/callback/")
BITRIX_OAUTH_BASE_URL = os.getenv("BITRIX_OAUTH_BASE_URL", "https://oauth.bitrix.info/oauth")
