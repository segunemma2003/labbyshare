"""
Django settings for labmyshare project - Works for both local and production
"""
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-kbe964))52lspgz7g4jf92bi5m84@$z2gum=q%_d&8jhzc=**h')

load_dotenv(os.path.join(BASE_DIR, '.env'))
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

# Environment detection
IS_PRODUCTION = not DEBUG or os.environ.get('ENVIRONMENT') == 'production'
IS_LOCAL = not IS_PRODUCTION

# Flexible host configuration
ALLOWED_HOSTS = ['*']
if IS_PRODUCTION:
    ALLOWED_HOSTS = [
        'backend.beautyspabyshea.co.uk',
        'localhost',
        '127.0.0.1',
        '31.97.57.199',  # Your server IP
    ]
else:
    # Local development
    ALLOWED_HOSTS = [
        'localhost',
        '127.0.0.1',
        '0.0.0.0',
        '*',  # Allow all hosts in development
    ]

# Add any additional hosts from environment
ADDITIONAL_HOSTS = os.environ.get('ADDITIONAL_HOSTS', '').split(',')
ALLOWED_HOSTS.extend([host.strip() for host in ADDITIONAL_HOSTS if host.strip()])

LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'drf_yasg',
    'django_redis',
    'django_celery_beat',
    'django_extensions',
]

LOCAL_APPS = [
    'accounts',
    'regions',
    'services',
    'professionals',
    'bookings',
    'payments',
    'notifications',
    'admin_panel',
    'health',
    'analytics',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'regions.middleware.RegionMiddleware',
]

ROOT_URLCONF = 'labmyshare.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'labmyshare.wsgi.application'

# Database configuration - flexible for local and production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'labmyshare_db'),
        'USER': os.environ.get('DB_USER', 'labmyshare'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'labmyshare2020'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'CONN_HEALTH_CHECKS': True,
    }
}

# Use SQLite for local development if PostgreSQL is not available
if IS_LOCAL and os.environ.get('USE_SQLITE', 'False').lower() == 'true':
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8}
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files configuration - works for both local and production
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redis Configuration - flexible for local and production
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50 if IS_LOCAL else 200,
                'retry_on_timeout': True,
                'health_check_interval': 60,
            },
            'SERIALIZER': 'django_redis.serializers.pickle.PickleSerializer',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        },
        'KEY_PREFIX': 'labmyshare',
        'TIMEOUT': 3600,
    }
}

# Use Redis for sessions in production, database for local
if IS_PRODUCTION:
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '2000/hour',
        'login': '10/min',
        'register': '5/min',
        'otp':'10/hour'
    },
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ] if IS_PRODUCTION else [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'EXCEPTION_HANDLER': 'utils.exceptions.custom_exception_handler',
}

# Swagger Configuration
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Token': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False,
    'JSON_EDITOR': True,
    'SUPPORTED_SUBMIT_METHODS': [
        'get', 'post', 'put', 'delete', 'patch'
    ],
}

# CORS Configuration - flexible for local and production
if IS_LOCAL:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
else:
    CORS_ALLOW_ALL_ORIGINS = True
    # CORS_ALLOWED_ORIGINS = [
    #     "https://backend.beautyspabyshea.co.uk",
    #     "http://backend.beautyspabyshea.co.uk",
    #     "https://app.labmyshare.com",
    #     "http://localhost:3000",
    #     "http://127.0.0.1:3000",
    # ]
    CORS_ALLOW_CREDENTIALS = True

# HTTPS/SSL Configuration - Only in production
if IS_PRODUCTION:
    # Trust proxy headers for HTTPS
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # CSRF trusted origins for HTTPS
    CSRF_TRUSTED_ORIGINS = [
        'https://backend.beautyspabyshea.co.uk',
        'http://backend.beautyspabyshea.co.uk',  # For fallback
    ]
    
    # SSL/HTTPS settings - only enforce in production with proper SSL
    USE_TLS = os.environ.get('USE_TLS', 'true').lower() == 'true'
    
    if USE_TLS:
        SECURE_SSL_REDIRECT = False  # Let Nginx handle redirects
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_BROWSER_XSS_FILTER = True
        SECURE_CONTENT_TYPE_NOSNIFF = True
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
    else:
        # Fallback for production without SSL
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False
else:
    # Local development - no HTTPS enforcement
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]

# Always set these for security
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Firebase Configuration
FIREBASE_CONFIG = {
    'type': 'service_account',
    'project_id': os.environ.get('FIREBASE_PROJECT_ID'),
    'private_key_id': os.environ.get('FIREBASE_PRIVATE_KEY_ID'),
    'private_key': os.environ.get('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
    'client_email': os.environ.get('FIREBASE_CLIENT_EMAIL'),
    'client_id': os.environ.get('FIREBASE_CLIENT_ID'),
    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
    'token_uri': 'https://oauth2.googleapis.com/token',
}

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@labmyshare.com')

# SMS Configuration (Twilio)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')

# Logging Configuration - Different for local and production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if IS_LOCAL else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'root': {
        'handlers': ['console'],
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'DEBUG' if IS_LOCAL else 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG' if IS_LOCAL else 'INFO',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'payments': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'notifications': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Add file logging only in production
if IS_PRODUCTION and not os.getenv('CI') and not os.getenv('GITHUB_ACTIONS'):
    LOGGING['handlers'].update({
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'django.log'),
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'django_error.log'),
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    })
    
    # Update loggers to use file handlers in production
    for logger_name in ['django', 'accounts', 'payments', 'notifications']:
        LOGGING['loggers'][logger_name]['handlers'] = ['console', 'file', 'error_file']

# Performance Settings
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Cache Keys and Timeouts
CACHE_KEYS = {
    'REGIONS': 'regions:all',
    'CATEGORIES': 'categories:region:{}',
    'SERVICES': 'services:region:{}:category:{}',
    'PROFESSIONALS': 'professionals:region:{}:service:{}',
    'USER_PROFILE': 'user:profile:{}',
    'AVAILABILITY': 'availability:professional:{}:region:{}:date:{}',
}

CACHE_TIMEOUTS = {
    'REGIONS': 3600 * 24,  # 24 hours
    'CATEGORIES': 3600 * 12,  # 12 hours  
    'SERVICES': 3600 * 6,  # 6 hours
    'PROFESSIONALS': 3600 * 2,  # 2 hours
    'USER_PROFILE': 3600,  # 1 hour
    'AVAILABILITY': 1800,  # 30 minutes
}

# # Print configuration info
# if DEBUG:
#     print(f"🔧 Django Configuration:")
#     print(f"   Environment: {'Production' if IS_PRODUCTION else 'Local Development'}")
#     print(f"   Debug: {DEBUG}")
#     print(f"   Database: {DATABASES['default']['ENGINE'].split('.')[-1]}")
#     print(f"   Allowed Hosts: {ALLOWED_HOSTS}")
#     print(f"   HTTPS: {'Enabled' if IS_PRODUCTION and globals().get('USE_TLS', False) else 'Disabled'}")
#     print(f"   Redis: {REDIS_URL}")
#     print(f"   Static Root: {STATIC_ROOT}")
