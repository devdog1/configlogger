"""
Django settings for oxidized_project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'oxidized-secret-key-change-in-production')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = ['*']

# Reverse Proxy & CSRF Configuration
# Support PROXY_URL or CSRF_TRUSTED_ORIGINS to allow proxy origin(s)
CSRF_TRUSTED_ORIGINS = []
_raw_origins = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if _raw_origins:
    CSRF_TRUSTED_ORIGINS.extend([origin.strip() for origin in _raw_origins.split(',') if origin.strip()])

_proxy_url = os.environ.get('PROXY_URL', '').strip()
if _proxy_url:
    # Ensure scheme is present
    if not (_proxy_url.startswith('http://') or _proxy_url.startswith('https://')):
        _proxy_url = f"https://{_proxy_url}"
    if _proxy_url not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_proxy_url)

# Always trust localhost by default for local development & previews
for default_origin in ['http://127.0.0.1:8000', 'http://localhost:8000', 'http://127.0.0.1:8080', 'http://localhost:8080']:
    if default_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(default_origin)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'oxidized_web',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'oxidized_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'oxidized_web' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'oxidized_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'oxidized'),
        'USER': os.environ.get('POSTGRES_USER', 'oxidized'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'oxidized'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'oxidized_web' / 'static',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login'
LOGIN_REDIRECT_URL = '/nodes'
LOGOUT_REDIRECT_URL = '/login'
