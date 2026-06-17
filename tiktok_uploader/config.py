import os


def _env_list(name, default):
    value = os.getenv(name, "").strip()
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "awhfxd65i4i468x8")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "QwlYmiutMspEQF266RnFoYFOtB6JaLAB")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://fb74c8b0281a8c.lhr.life").rstrip("/")
REDIRECT_URI = os.getenv("REDIRECT_URI", f"{PUBLIC_BASE_URL}/callback")
SCOPES = _env_list("TIKTOK_SCOPES", ["user.info.basic", "video.upload", "video.publish"])
TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_VIDEO_INIT = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_VIDEO_PUBLISH = "https://open.tiktokapis.com/v2/post/publish/video/publish/"
TIKTOK_QUERY_CREATOR = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "demo-secret-key-change-in-production")
PORT = int(os.getenv("PORT", "8080"))
DEBUG = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
