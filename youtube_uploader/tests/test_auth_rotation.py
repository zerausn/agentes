import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_support import install_uploader_dependency_stubs

install_uploader_dependency_stubs()

import teaser_uploader as teaser_uploader_module
import uploader as uploader_module


class AuthRotationResolutionTests(unittest.TestCase):
    def write_client_secret(self, path, client_id):
        path.write_text(
            json.dumps(
                {
                    "installed": {
                        "client_id": client_id,
                    }
                }
            ),
            encoding="utf-8",
        )

    def write_token(self, path, client_id, scopes):
        path.write_text(
            json.dumps(
                {
                    "client_id": client_id,
                    "client_secret": "secret",
                    "refresh_token": "refresh-token",
                    "scopes": scopes,
                }
            ),
            encoding="utf-8",
        )

    def test_uploader_lists_client_secrets_in_numeric_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            self.write_client_secret(credentials_dir / "client_secret_10.json", "client-10")
            self.write_client_secret(credentials_dir / "client_secret_2.json", "client-2")
            self.write_client_secret(credentials_dir / "client_secret_1.json", "client-1")

            with patch.object(uploader_module, "CREDENTIALS_DIR", credentials_dir):
                client_files = uploader_module._list_client_secret_files()

            self.assertEqual(
                [path.name for path in client_files],
                ["client_secret_1.json", "client_secret_2.json", "client_secret_10.json"],
            )

    def test_uploader_prefers_token_with_matching_client_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            client_secret = credentials_dir / "client_secret_3.json"
            fallback_token = credentials_dir / "token_1.json"
            expected_token = credentials_dir / "token_2.json"

            self.write_client_secret(client_secret, "client-3")
            self.write_token(fallback_token, "client-2", uploader_module.SCOPES)
            self.write_token(expected_token, "client-3", uploader_module.SCOPES)

            with patch.object(uploader_module, "CREDENTIALS_DIR", credentials_dir):
                resolved = uploader_module.resolve_creds_cache_file(client_secret, fallback_token)

            self.assertEqual(resolved, expected_token)

    def test_uploader_does_not_borrow_token_from_other_client(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            client_secret = credentials_dir / "client_secret_4.json"
            wrong_fallback = credentials_dir / "token_1.json"
            expected_new_token = credentials_dir / "token_3.json"

            self.write_client_secret(client_secret, "client-4")
            self.write_token(wrong_fallback, "client-2", uploader_module.SCOPES)
            self.write_token(credentials_dir / "token_2.json", "client-3", uploader_module.SCOPES)

            with patch.object(uploader_module, "CREDENTIALS_DIR", credentials_dir):
                resolved = uploader_module.resolve_creds_cache_file(client_secret, wrong_fallback)

            self.assertEqual(resolved, expected_new_token)

    def test_uploader_forces_new_token_when_only_client_3_and_4_tokens_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            client_secret = credentials_dir / "client_secret_2.json"
            expected_new_token = credentials_dir / "token_1.json"

            self.write_client_secret(client_secret, "client-2")
            self.write_token(credentials_dir / "token_2.json", "client-3", uploader_module.SCOPES)
            self.write_token(credentials_dir / "token_3.json", "client-4", uploader_module.SCOPES)

            with patch.object(uploader_module, "CREDENTIALS_DIR", credentials_dir):
                resolved = uploader_module.resolve_creds_cache_file(client_secret, expected_new_token)

            self.assertEqual(resolved, expected_new_token)

    def test_uploader_credential_pool_skips_clients_without_matching_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            self.write_client_secret(credentials_dir / "client_secret_1.json", "client-1")
            self.write_client_secret(credentials_dir / "client_secret_2.json", "client-2")
            self.write_client_secret(credentials_dir / "client_secret_3.json", "client-3")
            self.write_client_secret(credentials_dir / "client_secret_4.json", "client-4")
            self.write_token(credentials_dir / "token_2.json", "client-3", uploader_module.SCOPES)
            self.write_token(credentials_dir / "token_3.json", "client-4", uploader_module.SCOPES)

            with patch.object(uploader_module, "CREDENTIALS_DIR", credentials_dir):
                pool = uploader_module._build_credential_pool()

            self.assertEqual(
                [slot["client_name"] for slot in pool],
                ["client_secret_3.json", "client_secret_4.json"],
            )

    def test_teaser_lists_client_secrets_in_numeric_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            self.write_client_secret(credentials_dir / "client_secret_11.json", "client-11")
            self.write_client_secret(credentials_dir / "client_secret_2.json", "client-2")
            self.write_client_secret(credentials_dir / "client_secret_3.json", "client-3")

            with patch.object(teaser_uploader_module, "CREDENTIALS_DIR", credentials_dir):
                client_files = teaser_uploader_module._list_client_secret_files()

            self.assertEqual(
                [path.name for path in client_files],
                ["client_secret_2.json", "client_secret_3.json", "client_secret_11.json"],
            )

    def test_teaser_ignores_token_from_other_client_even_if_number_is_higher(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            client_secret = credentials_dir / "client_secret_2.json"
            expected_token = credentials_dir / "token_1.json"
            wrong_numbered_token = credentials_dir / "token_2.json"

            self.write_client_secret(client_secret, "client-2")
            self.write_token(expected_token, "client-2", teaser_uploader_module.SCOPES)
            self.write_token(wrong_numbered_token, "client-3", teaser_uploader_module.SCOPES)

            with patch.object(teaser_uploader_module, "CREDENTIALS_DIR", credentials_dir):
                resolved = teaser_uploader_module.resolve_token_cache_file(client_secret, key_index=1)

            self.assertEqual(resolved, expected_token)

    def test_teaser_forces_new_token_when_only_client_3_and_4_tokens_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            client_secret = credentials_dir / "client_secret_2.json"
            expected_new_token = credentials_dir / "token_1.json"

            self.write_client_secret(client_secret, "client-2")
            self.write_token(credentials_dir / "token_2.json", "client-3", teaser_uploader_module.SCOPES)
            self.write_token(credentials_dir / "token_3.json", "client-4", teaser_uploader_module.SCOPES)

            with patch.object(teaser_uploader_module, "CREDENTIALS_DIR", credentials_dir):
                resolved = teaser_uploader_module.resolve_token_cache_file(client_secret, key_index=1)

            self.assertEqual(resolved, expected_new_token)

    def test_teaser_credential_pool_skips_clients_without_matching_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_dir = Path(tmpdir)
            self.write_client_secret(credentials_dir / "client_secret_1.json", "client-1")
            self.write_client_secret(credentials_dir / "client_secret_2.json", "client-2")
            self.write_client_secret(credentials_dir / "client_secret_3.json", "client-3")
            self.write_client_secret(credentials_dir / "client_secret_4.json", "client-4")
            self.write_token(credentials_dir / "token_2.json", "client-3", teaser_uploader_module.SCOPES)
            self.write_token(credentials_dir / "token_3.json", "client-4", teaser_uploader_module.SCOPES)

            with patch.object(teaser_uploader_module, "CREDENTIALS_DIR", credentials_dir):
                pool = teaser_uploader_module._build_credential_pool()

            self.assertEqual(
                [slot["client_name"] for slot in pool],
                ["client_secret_3.json", "client_secret_4.json"],
            )


if __name__ == "__main__":
    unittest.main()
