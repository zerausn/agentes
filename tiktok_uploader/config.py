import os

# Sandbox creds (default)
SANDBOX_CLIENT_KEY = "sbawgooshw60ceibf2"
SANDBOX_CLIENT_SECRET = "cabF93Nh2eIgiafuqXzOsqZiZSEXwS55"

# Production creds (for when Content Posting API is approved)
PROD_CLIENT_KEY = "awhfxd65i4i468x8"
PROD_CLIENT_SECRET = "QwlYmiutMspEQF266RnFoYFOtB6JaLAB"

# Environment-level config
CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", SANDBOX_CLIENT_KEY)
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", SANDBOX_CLIENT_SECRET)
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://127.0.0.1:8080/callback")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8080")
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

scope_str = os.environ.get("TIKTOK_SCOPES", "user.info.basic,user.info.profile,user.info.stats,video.list")
SCOPES = [s.strip() for s in scope_str.split(",") if s.strip()]

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_VIDEO_INIT = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_VIDEO_PUBLISH = "https://open.tiktokapis.com/v2/post/publish/video/publish/"
TIKTOK_QUERY_CREATOR = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
