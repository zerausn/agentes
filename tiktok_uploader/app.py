import secrets
import requests
from urllib.parse import urlencode
from flask import Flask, redirect, request, session, render_template, jsonify, send_from_directory
import os
from werkzeug.middleware.proxy_fix import ProxyFix
from config import *

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

TOKENS = {}
SITE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "meta_uploader", "site"))


@app.route("/<path:filename>")
def serve_static_site(filename):
    allowed_files = ["privacy.html", "terms.html", "data-deletion.html", "styles.css"]
    if filename in allowed_files or filename.endswith(".txt"):
        return send_from_directory(SITE_DIR, filename)
    return "Not found", 404

def resolve_public_base_url():
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    proto = forwarded_proto.split(",", 1)[0].strip() or request.scheme
    forwarded_host = request.headers.get("X-Forwarded-Host", "")
    host = forwarded_host.split(",", 1)[0].strip() or request.host
    return f"{proto}://{host}".rstrip("/")


def resolve_redirect_uri():
    return f"{resolve_public_base_url()}/callback"


def start_login(scopes, scope_mode):
    csrf_state = secrets.token_urlsafe(16)
    redirect_uri = resolve_redirect_uri()
    session["csrf_state"] = csrf_state
    session["oauth_redirect_uri"] = redirect_uri
    session["oauth_scope_mode"] = scope_mode
    params = {
        "client_key": CLIENT_KEY,
        "response_type": "code",
        "scope": ",".join(scopes),
        "redirect_uri": redirect_uri,
        "state": csrf_state,
    }
    url = TIKTOK_AUTH_URL + "?" + urlencode(params)
    return redirect(url)


@app.route("/")
def index():
    user = session.get("user")
    redirect_uri = resolve_redirect_uri()
    return render_template("index.html", user=user, redirect_uri=redirect_uri)


@app.route("/login")
def login():
    return start_login(SCOPES, "full")


@app.route("/login/basic")
def login_basic():
    return start_login(["user.info.basic"], "basic")


@app.route("/callback")
def callback():
    redirect_uri = session.get("oauth_redirect_uri") or resolve_redirect_uri()
    scope_mode = session.get("oauth_scope_mode", "full")
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    error_desc = request.args.get("error_description")
    granted_scopes = request.args.get("scopes", "")
    print(f"[DEBUG] callback url={request.url}")
    print(f"[DEBUG] callback args: {dict(request.args)}")
    if error:
        return f"TikTok error: {error} - {error_desc}", 400
    if not code:
        if not request.args:
            return render_template("callback_bridge.html", redirect_uri=redirect_uri)
        return f"Error: no authorization code received from TikTok. Args: {dict(request.args)}", 400
    if state != session.pop("csrf_state", None):
        return "Error: state mismatch", 400
    body = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    print(f"[DEBUG] code={code} redirect_uri={redirect_uri}")
    resp = requests.post(TIKTOK_TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    print(f"[DEBUG] token status={resp.status_code}")
    print(f"[DEBUG] token response={resp.text[:500]}")
    data = resp.json()
    if "access_token" not in data:
        return f"Error getting token: {data}", 400
    token = data["access_token"]
    open_id = data["open_id"]
    TOKENS[open_id] = token
    session["user"] = {
        "open_id": open_id,
        "token": token,
        "scope_mode": scope_mode,
        "granted_scopes": granted_scopes,
    }
    session.pop("oauth_redirect_uri", None)
    session.pop("oauth_scope_mode", None)
    if scope_mode == "basic":
        return redirect("/")
    return redirect("/upload")


@app.route("/upload")
def upload_page():
    if "user" not in session:
        return redirect("/")
    info = requests.post(TIKTOK_QUERY_CREATOR, headers={
        "Authorization": f"Bearer {session['user']['token']}",
        "Content-Type": "application/json",
    }, json={}).json()
    max_duration = info.get("data", {}).get("max_video_post_duration_sec", 600)
    return render_template("upload.html", max_duration=max_duration)


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
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False)
