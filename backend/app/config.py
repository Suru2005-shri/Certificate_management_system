import os

def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

DATABASE_URL = env("DATABASE_URL")
KEYCLOAK_JWKS_URL = env("KEYCLOAK_JWKS_URL")
KEYCLOAK_ISSUER = env("KEYCLOAK_ISSUER")

MINIO_ENDPOINT = env("MINIO_ENDPOINT", "minio:9000")                  # backend -> MinIO (internal)
MINIO_PUBLIC_ENDPOINT = env("MINIO_PUBLIC_ENDPOINT", "localhost:9000")  # host used inside signed URLs (browser-reachable)
MINIO_ACCESS_KEY = env("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = env("MINIO_SECRET_KEY")
MINIO_SECURE = env("MINIO_SECURE", "false").lower() == "true"
# Signed URLs are opened by browsers: in production they must be https even though backend->storage is plain http inside Docker
MINIO_PUBLIC_SECURE = env("MINIO_PUBLIC_SECURE", "true" if MINIO_SECURE else "false").lower() == "true"
MINIO_BUCKET = env("MINIO_BUCKET", "student-certificates")

SIGNED_URL_SECONDS = 300
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PHOTOS = 5

ROLL_NO_PATTERN = env("ROLL_NO_PATTERN", r"^[A-Za-z0-9\-/]{3,20}$")
PHONE_PATTERN = r"^\+?[0-9]{10,13}$"
ALLOWED_EMAIL_DOMAINS = [d.strip().lower() for d in env("ALLOWED_EMAIL_DOMAINS").split(",") if d.strip()]
REQUIRE_PHONE_VERIFIED = env("REQUIRE_PHONE_VERIFIED", "false").lower() == "true"

MCAPTCHA_VERIFY_URL = env("MCAPTCHA_VERIFY_URL")   # e.g. http://mcaptcha:7000/api/v1/pow/siteverify
MCAPTCHA_SITE_KEY = env("MCAPTCHA_SITE_KEY")
MCAPTCHA_SECRET = env("MCAPTCHA_SECRET")

TRUST_PROXY = env("TRUST_PROXY", "true").lower() == "true"   # read client IP from X-Forwarded-For set by nginx
