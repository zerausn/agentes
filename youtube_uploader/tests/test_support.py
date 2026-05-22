import importlib.util
import json
import sys
import types


def _module_missing(module_name):
    try:
        return importlib.util.find_spec(module_name) is None
    except ModuleNotFoundError:
        return True


def install_uploader_dependency_stubs():
    if _module_missing("httplib2"):
        httplib2_module = types.ModuleType("httplib2")

        class HttpLib2Error(Exception):
            pass

        httplib2_module.HttpLib2Error = HttpLib2Error
        sys.modules["httplib2"] = httplib2_module

    if _module_missing("google.auth.transport.requests"):
        google_module = sys.modules.setdefault("google", types.ModuleType("google"))
        auth_module = sys.modules.setdefault("google.auth", types.ModuleType("google.auth"))
        transport_module = sys.modules.setdefault(
            "google.auth.transport",
            types.ModuleType("google.auth.transport"),
        )
        requests_module = types.ModuleType("google.auth.transport.requests")

        class Request:
            pass

        requests_module.Request = Request
        transport_module.requests = requests_module
        auth_module.transport = transport_module
        google_module.auth = auth_module
        sys.modules["google.auth.transport.requests"] = requests_module

    if _module_missing("google.oauth2.credentials"):
        google_module = sys.modules.setdefault("google", types.ModuleType("google"))
        oauth2_module = sys.modules.setdefault("google.oauth2", types.ModuleType("google.oauth2"))
        credentials_module = types.ModuleType("google.oauth2.credentials")

        class Credentials:
            def __init__(self):
                self.valid = True
                self.expired = False
                self.refresh_token = "stub-refresh-token"

            @classmethod
            def from_authorized_user_file(cls, *_args, **_kwargs):
                return cls()

            def refresh(self, *_args, **_kwargs):
                self.valid = True

            def to_json(self):
                return json.dumps({"client_id": "stub-client", "scopes": []})

        credentials_module.Credentials = Credentials
        oauth2_module.credentials = credentials_module
        google_module.oauth2 = oauth2_module
        sys.modules["google.oauth2.credentials"] = credentials_module

    if _module_missing("google_auth_oauthlib.flow"):
        oauthlib_module = sys.modules.setdefault(
            "google_auth_oauthlib",
            types.ModuleType("google_auth_oauthlib"),
        )
        flow_module = types.ModuleType("google_auth_oauthlib.flow")

        class InstalledAppFlow:
            def __init__(self):
                self.credentials = sys.modules["google.oauth2.credentials"].Credentials()

            @classmethod
            def from_client_secrets_file(cls, *_args, **_kwargs):
                return cls()

            def run_local_server(self, *_args, **_kwargs):
                return self.credentials

            def authorization_url(self, *_args, **_kwargs):
                return ("https://example.com/auth", None)

            def fetch_token(self, *_args, **_kwargs):
                return None

        flow_module.InstalledAppFlow = InstalledAppFlow
        oauthlib_module.flow = flow_module
        sys.modules["google_auth_oauthlib.flow"] = flow_module

    if _module_missing("googleapiclient.discovery"):
        googleapiclient_module = sys.modules.setdefault(
            "googleapiclient",
            types.ModuleType("googleapiclient"),
        )
        discovery_module = types.ModuleType("googleapiclient.discovery")

        def build(*_args, **_kwargs):
            return object()

        discovery_module.build = build
        googleapiclient_module.discovery = discovery_module
        sys.modules["googleapiclient.discovery"] = discovery_module

    if _module_missing("googleapiclient.errors"):
        googleapiclient_module = sys.modules.setdefault(
            "googleapiclient",
            types.ModuleType("googleapiclient"),
        )
        errors_module = types.ModuleType("googleapiclient.errors")

        class HttpError(Exception):
            def __init__(self, resp=None, content=b""):
                super().__init__("stub HttpError")
                self.resp = resp or types.SimpleNamespace(status=500)
                self.content = content

        errors_module.HttpError = HttpError
        googleapiclient_module.errors = errors_module
        sys.modules["googleapiclient.errors"] = errors_module

    if _module_missing("googleapiclient.http"):
        googleapiclient_module = sys.modules.setdefault(
            "googleapiclient",
            types.ModuleType("googleapiclient"),
        )
        http_module = types.ModuleType("googleapiclient.http")

        class MediaFileUpload:
            def __init__(self, *_args, **_kwargs):
                self._fd = None

            def size(self):
                return 0

        http_module.MediaFileUpload = MediaFileUpload
        googleapiclient_module.http = http_module
        sys.modules["googleapiclient.http"] = http_module
