import os
import socket
import ipaddress
from django.apps import AppConfig
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(env_path):
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def get_env_list(name, default=None):
    raw_value = os.getenv(name, '')
    if not raw_value:
        return list(default or [])
    return [item.strip() for item in raw_value.split(',') if item.strip()]


def get_env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def get_local_hosts():
    hosts = {'127.0.0.1', 'localhost', '0.0.0.0'}

    try:
        hostname = socket.gethostname()
        if hostname:
            hosts.add(hostname)
        fqdn = socket.getfqdn()
        if fqdn:
            hosts.add(fqdn)
        for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            address = sockaddr[0]
            if address:
                hosts.add(address)
    except OSError:
        pass

    return sorted(hosts)


def is_valid_host_for_origin(host):
    if not host or host in {'*', '0.0.0.0'}:
        return False

    candidate = host.strip().lstrip('.').split(':', 1)[0]
    if not candidate:
        return False

    if candidate.lower() == 'localhost':
        return True

    try:
        ipaddress.ip_address(candidate)
        return True
    except ValueError:
        pass

    return all(part and part.replace('-', '').isalnum() for part in candidate.split('.'))


def build_csrf_trusted_origins(hosts, scheme):
    valid_scheme = scheme if scheme in {'http', 'https'} else 'https'
    origins = []
    for host in hosts:
        normalized = host.strip().lstrip('.')
        if not is_valid_host_for_origin(normalized):
            continue
        origins.append(f'{valid_scheme}://{normalized}')
    return sorted(set(origins))


load_env_file(BASE_DIR / '.env')

SECRET_KEY = 'django-insecure-9qeew0dcs+4ti&1+lg_q1bc3gd-gyhq%7sb%whr%eb=ou5n+0q'

DEBUG = get_env_bool('DJANGO_DEBUG', True)

configured_hosts = get_env_list('DJANGO_ALLOWED_HOSTS', [])
ALLOWED_HOSTS = sorted(set(configured_hosts + get_local_hosts()))

if DEBUG:
    ALLOWED_HOSTS.append('*')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'conveniencia_bobesponjaApp.apps.ConvenienciaBobesponjaappConfig',
    'django.contrib.humanize',

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

ROOT_URLCONF = 'conveniencia_bobesponja.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',    
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'conveniencia_bobesponja.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = os.getenv('DJANGO_TIME_ZONE', 'America/Sao_Paulo')

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = (
    './static',
)

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login URL redirection
LOGIN_URL = 'login'

# Email configuration
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD else 'django.core.mail.backends.console.EmailBackend'
)
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@sistema-vendas.local')

# HTTPS defaults and security
DEFAULT_SCHEME = os.getenv('DJANGO_DEFAULT_SCHEME', 'https').strip().lower() or 'https'
FORCE_HTTPS = get_env_bool('DJANGO_FORCE_HTTPS', False)

configured_csrf_origins = get_env_list('DJANGO_CSRF_TRUSTED_ORIGINS', [])
auto_csrf_origins = build_csrf_trusted_origins(ALLOWED_HOSTS, DEFAULT_SCHEME)
CSRF_TRUSTED_ORIGINS = sorted(set(configured_csrf_origins + auto_csrf_origins))

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = FORCE_HTTPS

SESSION_COOKIE_SECURE = FORCE_HTTPS
CSRF_COOKIE_SECURE = FORCE_HTTPS

if FORCE_HTTPS:
    SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
