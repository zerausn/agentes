import secrets
import base64
import hashlib
import requests
from urllib.parse import urlencode
from flask import Flask, redirect, request, session, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import *

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

TOKENS = {}

PROD_CLIENT_KEY = "awhfxd65i4i468x8"
PROD_CLIENT_SECRET = "QwlYmiutMspEQF266RnFoYFOtB6JaLAB"
SANDBOX_CLIENT_KEY = "sbawgooshw60ceibf2"
SANDBOX_CLIENT_SECRET = "cabF93Nh2eIgiafuqXzOsqZiZSEXwS55"


def _creds():
    return SANDBOX_CLIENT_KEY, SANDBOX_CLIENT_SECRET


def dynamic_redirect_uri():
    return request.url_root.rstrip("/") + "/callback"


@app.route("/")
def index():
    user = session.get("user")
    return render_template("index.html", user=user)


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@app.route("/login")
def login():
    csrf_state = secrets.token_urlsafe(16)
    session["csrf_state"] = csrf_state
    code_verifier, code_challenge = _pkce_pair()
    session["code_verifier"] = code_verifier
    ck, cs = _creds()
    redirect_uri = dynamic_redirect_uri()
    params = {
        "client_key": ck,
        "response_type": "code",
        "scope": ",".join(SCOPES),
        "redirect_uri": redirect_uri,
        "state": csrf_state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = TIKTOK_AUTH_URL + "?" + urlencode(params)
    return redirect(url)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if state != session.pop("csrf_state", None):
        return "Error: state mismatch", 400
    ck, cs = _creds()
    redirect_uri = dynamic_redirect_uri()
    code_verifier = session.pop("code_verifier", None)
    resp = requests.post(TIKTOK_TOKEN_URL, data={
        "client_key": ck,
        "client_secret": cs,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier or "",
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    data = resp.json()
    if "access_token" not in data:
        return f"Error getting token: {data}", 400
    token = data["access_token"]
    open_id = data["open_id"]
    TOKENS[open_id] = token
    session["user"] = {"open_id": open_id, "token": token}
    return redirect("/upload")


@app.route("/upload")
def upload_page():
    if "user" not in session:
        return redirect("/")
    max_duration = 600
    try:
        info = requests.post(TIKTOK_QUERY_CREATOR, headers={
            "Authorization": f"Bearer {session['user']['token']}",
            "Content-Type": "application/json",
        }, json={}).json()
        if "data" in info:
            max_duration = info["data"].get("max_video_post_duration_sec", 600)
    except Exception:
        pass
    return render_template("upload.html", max_duration=max_duration, sandbox=True)


@app.route("/api/init-upload", methods=["POST"])
def init_upload():
    if "user" not in session:
        return jsonify({"error": "not logged in"}), 401
    size = request.json.get("size", 0)
    resp = requests.post(TIKTOK_VIDEO_INIT, headers={
        "Authorization": f"Bearer {session['user']['token']}",
        "Content-Type": "application/json",
    }, json={
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,
            "total_chunk_count": 1,
        }
    })
    return jsonify(resp.json())


@app.route("/api/upload-file", methods=["POST"])
def upload_file():
    upload_url = request.form.get("upload_url")
    file = request.files.get("file")
    if not upload_url or not file:
        return jsonify({"error": "missing upload_url or file"}), 400
    file.seek(0)
    resp = requests.put(upload_url, data=file.read(),
        headers={"Content-Type": "video/mp4"})
    return jsonify({"status": resp.status_code, "reason": resp.reason})


@app.route("/api/publish", methods=["POST"])
def publish():
    if "user" not in session:
        return jsonify({"error": "not logged in"}), 401
    publish_id = request.json.get("publish_id")
    privacy_level = request.json.get("privacy_level", "SELF_ONLY")
    title = request.json.get("title", "")
    resp = requests.post(TIKTOK_VIDEO_PUBLISH, headers={
        "Authorization": f"Bearer {session['user']['token']}",
        "Content-Type": "application/json",
    }, json={
        "post_info": {
            "publish_id": publish_id,
            "privacy_level": privacy_level,
            "title": title,
        }
    })
    return jsonify(resp.json())


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
